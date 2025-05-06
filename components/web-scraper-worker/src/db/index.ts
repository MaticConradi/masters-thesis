import { config } from "dotenv"
config()

if (!process.env.DATABASE_URL) {
	throw new Error("DATABASE_URL is required")
}

import pgPromise from "pg-promise";

const pgp = pgPromise();
export const db = pgp(process.env.DATABASE_URL);