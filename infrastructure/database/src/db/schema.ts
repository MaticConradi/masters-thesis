import { integer, pgTable, text, timestamp } from "drizzle-orm/pg-core";

export const papersWithCodeTasksTable = pgTable("papers_with_code_tasks", {
	url: text("url").primaryKey(),
	count: integer("count").notNull().default(0),
	updatedAt: timestamp("updated_at").defaultNow()
})

export const proxiesTable = pgTable("proxies", {
	ip: text("ip").primaryKey(),
	username: text("username").notNull(),
	password: text("password").notNull(),
})