import { config } from "dotenv"
config()

import express from "express"
import { JobsClient } from "@google-cloud/run";

const client = new JobsClient()

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
	const name = `projects/${process.env.PROJECT_ID}/locations/${process.env.REGION}/jobs/${process.env.JOB_NAME}`;

	const request = {
		name,
		overrides: {
			containerOverrides: [
				{
					args: ['scrape-papers-with-code-papers'],
				},
			],
			taskCount: 1
		},
	};

	await client.runJob(request);
}

const app = express()

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