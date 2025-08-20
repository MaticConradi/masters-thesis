import { integer, pgTable, primaryKey, real, serial, text, timestamp } from "drizzle-orm/pg-core";

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

export const documentsTable = pgTable("documents", {
	id: serial("id").primaryKey(),
	document: text("document").unique().notNull()
})

export const sparseIndexTable = pgTable("sparse_index", {
	term: integer("term").notNull(),
	document_id: integer("document_id").notNull().references(() => documentsTable.id),
	score: real("score").notNull()
}, (table) => [
	primaryKey({ columns: [table.term, table.document_id] })
])