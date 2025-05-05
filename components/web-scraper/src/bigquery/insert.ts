import { articlesTable } from "./index.js";

type Article = {
	url: string;
	title: string;
	text: string;
	origin: string;
}

export async function insertArticleIntoBigQuery(row: Article) {
	try {
		await articlesTable.insert(row);
	} catch (error) {
		console.error('Error inserting into BigQuery:', error);
		throw error;
	}
}