import { config } from "dotenv"
config()

import { Page } from "puppeteer-core"
import { getBrowser, newPage } from "./puppeteer/browser.js"
import { fetchPapersWithCodeTasks, updatePapersWithCodeTask } from "./db/queries/papers-with-code.js"
import { PaperMetadata, Result } from "./types.js"
import { Storage } from "@google-cloud/storage"
import { createHash } from "crypto"
import { getRandomProxy } from "./db/queries/proxies.js"

const storage = new Storage()
const bucket = storage.bucket(process.env.ML_PAPERS_BUCKET_NAME!)

function computeFileHash(origin: string): string {
	return `${createHash("md5").update(origin).digest("base64url")}.pdf`
}

/**
 * Obtains an exhaustive list of tasks and subtasks from the SOTA page of Papers with Code.
 *
 * @returns {Promise<void>} A promise that resolves when the scraping is complete
 */
async function scrapePapersWithCodeTasks() {
	const tasks = await fetchPapersWithCodeTasks()
	console.log(`Found ${tasks.size} existing tasks`)

	const proxy = await getRandomProxy()
	if (!proxy) {
		throw new Error("No proxy available")
	}

	console.log(`Using proxy: ${proxy.ip}`)
	const browser = await getBrowser(proxy.ip)
	console.log("Chrome browser is ready")
	const page = await newPage(browser, proxy.username, proxy.password)
	await page.goto("https://paperswithcode.com/sota", { waitUntil: "domcontentloaded" })

	console.log("Scraping SOTA page...")

	const areas = []
	const taskCards = await page.$$(".sota-all-tasks")
	for (const taskCard of taskCards) {
		const url = await taskCard.$("a").then(a => a?.getProperty("href").then(prop => prop.jsonValue()))
		if (!url) {
			continue
		}

		areas.push(url)
	}

	console.log(`Found ${areas.length} areas, scraping categories...`)

	const categories = []
	for (const url of areas) {
		await page.goto(url, { waitUntil: "domcontentloaded" })

		const taskCards = await page.$$(".sota-all-tasks")
		for (const taskCard of taskCards) {
			const url = await taskCard.$("a").then(a => a?.getProperty("href").then(prop => prop.jsonValue()))
			if (!url) {
				continue
			}

			categories.push(url)
		}

		const cards = await page.$$(".card")
		for (const card of cards) {
			const url = await card.$("a").then(a => a?.getProperty("href").then(prop => prop.jsonValue()))
			const countText = await card.$$(".text-muted").then(spans => spans[1]?.getProperty("innerText").then(prop => prop.jsonValue()))
			if (!url) {
				continue
			}

			const count = parseInt((countText as string)?.replace(/[^0-9]/g, "")) || 0

			console.log(`${url}: ${count}`)
			tasks.set(url, count)
		}
	}

	console.log(`Found ${categories.length} categories, scraping tasks...`)

	for (const url of categories) {
		await page.goto(url, { waitUntil: "domcontentloaded" })

		const cards = await page.$$(".card")
		for (const card of cards) {
			const url = await card.$("a").then(a => a?.getProperty("href").then(prop => prop.jsonValue()))
			const countText = await card.$$(".text-muted").then(spans => spans[1]?.getProperty("innerText").then(prop => prop.jsonValue()))
			if (!url) {
				continue
			}

			const count = parseInt((countText as string)?.replace(/[^0-9]/g, "")) || 0

			console.log(`${url}: ${count}`)
			tasks.set(url, count)
		}
	}

	console.log(`Found ${tasks.size} tasks, updating database...`)

	for (const [url, count] of tasks.entries()) {
		await updatePapersWithCodeTask(url, count)
	}

	await browser.close()
}

/**
 * Scrapes the URLs of papers from the Papers with Code website and processes them.
 *
 * @param {string | undefined} task - The specific task to scrape papers for, or undefined to scrape all tasks
 * @returns {Promise<number>} The number of papers processed
 */
async function scrapePapersWithCodePapers(task: string | undefined): Promise<number> {
	const start = Date.now()
	let processedPaperCount = 0

	const tasks = await fetchPapersWithCodeTasks()
	console.log(`Found ${tasks.size} existing tasks`)

	const proxy = await getRandomProxy()
	if (!proxy) {
		throw new Error("No proxy available")
	}

	console.log(`Using proxy: ${proxy.ip}`)
	const browser = await getBrowser(proxy.ip)
	console.log("Chrome browser is ready")
	const page = await newPage(browser, proxy.username, proxy.password)

	console.log(`Found ${tasks.size} ML tasks`)

	let i = 1
	for (const [url, count] of tasks.entries()) {
		if (task && url !== task) {
			i += 1
			continue
		}

		const pages = Math.min(Math.ceil(count / 10), 20)
		console.log(`${i++}/${tasks.size}: ${url} (${pages} pages)`)

		// Reference of papers fetched in the previous iteration
		let processedPapers: string[] = []

		for (let j = 1; j <= pages; j++) {
			await page.goto(`${url}?page=${j}`, { waitUntil: "domcontentloaded" })

			const paperCards = await page.$$(".infinite-item.paper-card")
			if (paperCards.length === 0) {
				console.log(`No paper cards found on page ${j} of ${url}`)
				break
			}

			const papers: { origin: string, title: string }[] = []
			for (const paperCard of paperCards) {
				const titleElement = await paperCard.$("h1 a")
				if (!titleElement) {
					console.log("No title element found, skipping paper")
					continue
				}

				// Get the title and URL of the paper
				const origin = await titleElement.getProperty("href").then(prop => prop.jsonValue())
				const title = await titleElement.getProperty("innerText").then(prop => prop.jsonValue())

				if (processedPapers.includes(origin)) {
					continue
				}

				processedPapers.push(origin)

				papers.push({ origin, title })
			}

			for (const { origin, title } of papers) {
				// Stop if the time limit of 23 hours and 55 minutes is reached
				if (Date.now() - start > 86100 * 1000) {
					console.log("Time limit reached, stopping scraping")
					await browser.close()
					return processedPaperCount
				}

				const filename = computeFileHash(origin)
				const [exists] = await bucket.file(filename).exists()
				if (exists) {
					continue
				}

				await page.goto(origin, { waitUntil: "domcontentloaded" })

				const linkButton = await page.$("a.badge.badge-light")
				if (!linkButton) {
					console.log("No link button found, skipping paper")
					continue
				}

				// Get the URL of the PDF
				const url = await linkButton.getProperty("href").then(prop => prop.jsonValue())

				// Get associated metadata
				const metadata = await scrapeMetadata(page, origin, title)

				// Asynchronously upload the PDF to GCS
				uploadPDFToGCS(filename, url, metadata)

				processedPaperCount += 1
			}
		}
	}

	await browser.close()

	return processedPaperCount
}

async function uploadPDFToGCS(filename: string, url: string, metadata: PaperMetadata) {
	try {
		const response = await fetch(url)
		if (!response.ok) {
			return
		}

		const buffer = await response.arrayBuffer()

		const file = bucket.file(filename)
		await file.save(Buffer.from(buffer), {
			contentType: 'application/pdf',
			public: false,
			metadata: {
				metadata: {
					tasks: JSON.stringify(metadata.tasks),
					datasets: JSON.stringify(metadata.datasets),
					methods: JSON.stringify(metadata.methods),
					results: JSON.stringify(metadata.results)
				}
			}
		})
	} catch (error) {
		console.error(`Error downloading or uploading file ${filename}:`, error)
	}
}

async function scrapeMetadata(page: Page, origin: string, title: string): Promise<PaperMetadata> {
	const taskDiv = await page.$(".paper-tasks")
	const datasetsDiv = await page.$(".paper-datasets")
	const evaluationDiv = await page.$("#evaluation")
	const methodsDiv = await page.$(".method-section")

	const tasks = await taskDiv?.$$("a").then(anchors =>
		Promise.all(
			anchors
				.map(a => a.getProperty("innerText")
					.then(prop => prop.jsonValue())
					.then(value => value.trim()))
		).then(values => values.filter(value => !!value))
	)
	const datasets = await datasetsDiv?.$$("a").then(anchors =>
		Promise.all(
			anchors
				.map(a => a.getProperty("innerText")
					.then(prop => prop.jsonValue())
					.then(value => value.trim()))
		).then(values => values.filter(value => !!value && value !== "Add Datasets"))
	)

	const methods = await methodsDiv?.$$("a").then(anchors =>
		Promise.all(
			anchors
				.map(a => a.getProperty("innerText")
					.then(prop => prop.jsonValue())
					.then(value => value.trim()))
		).then(values => values.filter(value => !!value && value !== "relevant methods here"))
	)

	const results: Result[] = []
	let cache: {
		popLength?: number,
		task?: string,
		dataset?: string,
		model?: string,
	} = {}

	const rows = await evaluationDiv?.$$("tr")
	for (let i = 1; i < (rows?.length ?? 0); i++) {
		const cells = await rows![i].$$("td")

		if (!cache.popLength) {
			let popLength = 0
			while (cells.length > 6) {
				cells.pop()
				popLength++
			}
			cache.popLength = popLength
		} else {
			for (let _ = 0; _ < cache.popLength; _++) {
				cells.pop()
			}
		}

		const rank = await cells.pop()!.getProperty("innerText").then(prop => prop.jsonValue()).then(value => value.trim())
		const value = await cells.pop()!.getProperty("innerText").then(prop => prop.jsonValue()).then(value => value.trim())
		const metric = await cells.pop()!.getProperty("innerText").then(prop => prop.jsonValue()).then(value => value.trim())
		let model = await cells.pop()?.getProperty("innerText").then(prop => prop.jsonValue()).then(value => value.trim())
		let dataset = await cells.pop()?.getProperty("innerText").then(prop => prop.jsonValue()).then(value => value.trim())
		let task = await cells.pop()?.getProperty("innerText").then(prop => prop.jsonValue()).then(value => value.trim())

		if (task) {
			cache.task = task
		} else {
			task = cache.task
		}
		if (dataset) {
			cache.dataset = dataset
		} else {
			dataset = cache.dataset
		}
		if (model) {
			cache.model = model
		} else {
			model = cache.model
		}

		if (!task || !dataset || !model) {
			console.log(`Missing task, dataset or model for ${page.url()} at row ${i}`)
			continue
		}

		const result = {
			task,
			dataset,
			model,
			metric,
			value: value,
			rank: parseInt(rank.replace(/[^0-9]/g, ""))
		}
		results.push(result)
	}

	return {
		title,
		origin,
		tasks: tasks ?? [],
		datasets: datasets ?? [],
		results: results ?? [],
		methods: methods ?? []
	}
}

async function main() {
	const args = process.argv.slice(2) // Skip 'node' and script path

	if (args.length === 0) {
		console.error("Please provide an argument: 'scrape-papers-with-code-tasks' or 'scrape-papers-with-code-papers'")
		process.exit(1)
	}

	const command = args[0]

	try {
		if (command === 'scrape-papers-with-code-tasks') {
			console.log("Scraping Papers with Code tasks...")
			await scrapePapersWithCodeTasks()
			console.log("Tasks updated successfully.")
		} else if (command === 'scrape-papers-with-code-papers') {
			const task = args[1]
			console.log(`Scraping Papers with Code papers for task: ${task || "all tasks"}`)
			const count = await scrapePapersWithCodePapers(task)
			console.log(`Papers processed: ${count}`)
		} else {
			console.error(`Unknown command: ${command}. Available commands: 'scrape-papers-with-code-tasks', 'scrape-papers-with-code-papers'`)
			process.exit(1)
		}
		process.exit(0)
	} catch (error) {
		console.error(`Error executing command '${command}':`, error)
		process.exit(1)
	}
}

main()

process.on('SIGINT', async () => {
	console.log('Shutting down...');
	process.exit(0);
});