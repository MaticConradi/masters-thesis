import { db } from "../index.js";
import { TableTypes } from "../schema.js";

export async function getRandomProxy() {
	return db.oneOrNone<TableTypes["proxies"]["select"]>(`
		SELECT * FROM proxies
		ORDER BY RANDOM()
		LIMIT 1
	`);
}