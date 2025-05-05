import { bigquery } from "./index.js";

export async function readUrlsFromBigQuery(): Promise<{ url: string, origin: string }[]> {
	try {
		const query = `
			SELECT url, origin
			FROM \`personal-sandbox-403414.mc_magistrska.articles\`
		`;

		const [rows] = await bigquery.query(query);

		return rows
	} catch (error) {
		console.error('Error reading from BigQuery:', error);
		throw error;
	}
}