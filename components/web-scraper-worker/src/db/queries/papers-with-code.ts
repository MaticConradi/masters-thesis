import { db } from "../index.js";
import { TableTypes } from "../schema.js";

export async function fetchPapersWithCodeTasks() {
	const tasks = await db.any<TableTypes["papers_with_code_tasks"]["select"]>(`
		SELECT * FROM papers_with_code_tasks
	`);

	const tasksMap = new Map<string, number>();
	for (const task of tasks) {
		tasksMap.set(task.url, task.count);
	}
	return tasksMap;
}

export async function updatePapersWithCodeTask(url: string, count: number) {
	return await db.none(`
		INSERT INTO papers_with_code_tasks (url, count)
		VALUES ($1, $2)
		ON CONFLICT (url) DO UPDATE
		SET count = $2, updated_at = NOW()
	`, [url, count]);
}