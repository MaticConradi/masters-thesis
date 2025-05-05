import { integer, pgTable, text, timestamp } from "drizzle-orm/pg-core";

export const papersWithCodeTasksTable = pgTable("papers_with_code_tasks", {
	url: text("url").primaryKey(),
	count: integer("count").notNull().default(0),
	updatedAt: timestamp("updated_at").defaultNow()
})