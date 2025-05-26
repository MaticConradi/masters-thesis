import { config } from "dotenv"
config()

import express from "express"
import { JobsClient } from "@google-cloud/run";
import { fetchPapersWithCodeTasks } from "./db/queries/papers-with-code.js";
import { updateProxies } from "./db/queries/proxies.js";

const client = new JobsClient()

/**
 * Update proxy list
 */
async function updateProxyList() {
	if (!process.env.PROXY_LIST_URL) {
		throw new Error("PROXY_LIST_URL environment variable is not set");
	}

	const response = await fetch(process.env.PROXY_LIST_URL)
	if (!response.ok) {
		throw new Error("Failed to fetch proxies")
	}

	const proxies = await response.text().then(text => {
		return text.trim().split("\n")
			.map(line => {
				const [ip, port, username, password] = line.trim().split(":")
				return { ip: `${ip}:${port}`, username, password }
			})
	})

	await updateProxies(proxies);
}

/**
 * Obtains an exhaustive list of tasks and subtasks from the SOTA page of Papers with Code.
 *
 * @returns {Promise<void>} A promise that resolves when the job has been submitted.
 */
async function scrapePapersWithCodeTasks() {
	const name = `projects/${process.env.PROJECT_ID}/locations/${process.env.REGION}/jobs/${process.env.JOB_NAME}`;

	const request = {
		name,
		overrides: {
			containerOverrides: [
				{
					args: ['scrape-papers-with-code-tasks'],
				},
			],
			taskCount: 1
		},
	};

	await client.runJob(request);
}

/**
 * Scrapes the URLs of papers from the Papers with Code website and processes them.
 *
 * @returns {Promise<void>} A promise that resolves when the job has been submitted.
 */
async function processPapers(): Promise<void> {
	const tasks = await fetchPapersWithCodeTasks()

	const name = `projects/${process.env.PROJECT_ID}/locations/${process.env.REGION}/jobs/${process.env.JOB_NAME}`;

	for (const url of tasks.keys()) {
		const request = {
			name,
			overrides: {
				containerOverrides: [
					{
						args: ['scrape-papers-with-code-papers', url],
					},
				],
				taskCount: 1
			},
		};
		await client.runJob(request);
		await new Promise(resolve => setTimeout(resolve, 500));
	}
}

const app = express()

app.get('/proxy/update', async (req, res) => {
	console.log("Received request for /proxy/update")
	try {
		await updateProxyList();
		res.json({ message: "Proxy list updated successfully" });
	} catch (error) {
		console.error("Error in /proxy/update endpoint:", error);
		res.status(500).send({ message: "Failed to update proxy list", error: error });
	}
});

app.get('/papers-with-code/update-tasks', async (req, res) => {
	console.log("Received request for /papers-with-code/update-tasks")
	try {
		const count = await scrapePapersWithCodeTasks()
		res.send({ message: "Job started", count: count });
	} catch (error) {
		console.error("Error in /papers-with-code/update-tasks endpoint:", error);
		res.status(500).send({ message: "Failed to start processing job", error: error });
	}
});

app.get('/papers-with-code/process-papers', async (req, res) => {
	console.log("Received request for /papers-with-code/process-papers")
	try {
		await processPapers();
		res.json({ message: "Job started" });
	} catch (error) {
		console.error("Error in /papers-with-code/process-papers endpoint:", error);
		res.status(500).send({ message: "Failed to start processing job", error: error });
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