import { config } from "dotenv"
config()

import express from "express"
import { get_browser, new_page } from "./puppeteer/browser.js"
import { Page } from "puppeteer"
import { readUrlsFromBigQuery } from "./bigquery/read.js"
import { getRandomProxy } from "./utils/proxies.js"
import { fetchPapersWithCodeTasks, updatePapersWithCodeTask } from "./db/queries/papers-with-code.js"
import { Result } from "./types.js"

if (!process.env.PROXY_LIST_URL) {
	console.error("PROXY_LIST_URL is not set")
	process.exit(1)
}

/**
 * Obtains an exhaustive list of tasks and subtasks from the SOTA page of Papers with Code.
 *
 * @returns {Promise<void>} A promise that resolves when the scraping is complete
 */
async function scrapePapersWithCodeTasks() {
	const tasks = await fetchPapersWithCodeTasks()

	const proxy = await getRandomProxy()
	const browser = await get_browser(proxy.ip)
	const page = await new_page(browser, proxy.username, proxy.password)
	await page.goto("https://paperswithcode.com/sota", { waitUntil: "domcontentloaded" })

	const areas = []
	const taskCards = await page.$$(".sota-all-tasks")
	for (const taskCard of taskCards) {
		const url = await taskCard.$("a").then(a => a?.getProperty("href").then(prop => prop.jsonValue()))
		if (!url) {
			continue
		}

		areas.push(url)
	}

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

	for (const [url, count] of tasks.entries()) {
		await updatePapersWithCodeTask(url, count)
	}
}

/**
 * Scrapes the URLs of papers from the Papers with Code website and processes them.
 *
 * @returns {Promise<void>} A promise that resolves when the scraping is complete
 */
async function processPapers() {
	const existing = await readUrlsFromBigQuery()

	const tasks = await fetchPapersWithCodeTasks()

	const proxy = await getRandomProxy()
	const browser = await get_browser(proxy.ip)
	const page = await new_page(browser, proxy.username, proxy.password)

	console.log(`Found ${tasks.size} ML tasks`)

	let i = 1
	for (const [url, count] of tasks.entries()) {
		const pages = Math.min(Math.ceil(count / 10), 20)
		console.log(`${i++}/${tasks.size}: ${url} (${pages} pages)`)

		// Reference of papers fetched in the previous iteration
		let processedPapers: string[] = []

		for (let j = 1; j <= pages; j++) {
			await page.goto(`${url}?page=${j}`, { waitUntil: "domcontentloaded" })

			const paperCards = await page.$$(".infinite-item.paper-card")
			if (paperCards.length === 0) {
				break
			}

			let foundNewPapers = false
			for (const paperCard of paperCards) {
				const titleElement = await paperCard.$("h1 a")
				if (!titleElement) {
					continue
				}

				// Get the title and URL of the paper
				const origin = await titleElement.getProperty("href").then(prop => prop.jsonValue())
				const title = await titleElement.getProperty("innerText").then(prop => prop.jsonValue())

				if (existing.some(entry => entry.origin === origin) || processedPapers.includes(origin)) {
					continue
				}

				processedPapers.push(origin)
				foundNewPapers = true
				await page.goto(origin, { waitUntil: "domcontentloaded" })

				const linkButton = await page.$("a.badge.badge-light")
				if (!linkButton) {
					continue
				}

				// Get the URL of the PDF
				const url = await linkButton.getProperty("href").then(prop => prop.jsonValue())

				// TODO: PROCESS PDF

				// Get associated metadata
				const metadata = await scrapeMetadata(page)
			}

			if (!foundNewPapers) {
				break
			}
		}
	}

	await browser.close()
}

async function scrapeMetadata(page: Page): Promise<{
	tasks: string[],
	datasets: string[],
	results: Result[],
	methods: string[]
}> {
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
		tasks: tasks ?? [],
		datasets: datasets ?? [],
		results: results ?? [],
		methods: methods ?? []
	}
}

const app = express()

app.get('/papers-with-code/update-tasks', async (req, res) => {
	console.log("Received request for /papers-with-code/update-tasks")
	try {
		await scrapePapersWithCodeTasks()
		res.send({ message: "Tasks updated" });
	} catch (error) {
		console.error("Error in /papers-with-code/update-tasks endpoint:", error);
		res.status(500).send({ message: "Failed to update tasks", error: error });
	}
});

app.get('/papers-with-code/process-papers', async (req, res) => {
	console.log("Received request for /papers-with-code/process-papers")
	try {
		await processPapers();
		res.json({ message: "Papers processed" });
	} catch (error) {
		console.error("Error in /papers-with-code/process-papers endpoint:", error);
		res.status(500).send({ message: "Failed to process papers", error: error });
	}
});

const port = process.env.PORT || 3000
app.listen(port, () => {
	console.log(`Scraper server listening on port ${port}`);
});

// Graceful shutdown
process.on('SIGINT', async () => {
	console.log('Shutting down server...');
	process.exit(0);
});