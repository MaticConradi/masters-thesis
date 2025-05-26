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