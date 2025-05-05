export async function getRandomProxy() {
	const response = await fetch(process.env.PROXY_LIST_URL!)
	if (!response.ok) {
		throw new Error("Failed to fetch proxies")
	}

	const proxies = await response.text().then(text => {
		return text.split("\n")
			.map(line => {
				const [ip, port, username, password] = line.trim().split(":")
				return { ip: `${ip}:${port}`, username, password }
			})
	})

	return proxies[Math.floor(Math.random() * proxies.length)]
}