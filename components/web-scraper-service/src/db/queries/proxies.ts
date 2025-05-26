import { db } from "../index.js";

export async function updateProxies(proxies: { ip: string, username: string, password: string }[]): Promise<void> {
	await db.tx(async (tx) => {
		await tx.none("DELETE FROM proxies");
		for (const proxy of proxies) {
			await tx.none(
				"INSERT INTO proxies (ip, username, password) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
				[proxy.ip, proxy.username, proxy.password]
			);
		}
	});
}