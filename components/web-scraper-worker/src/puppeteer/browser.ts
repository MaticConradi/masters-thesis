import puppeteer, { Browser } from "puppeteer-core"

const EXTENSION_PATH = "extensions/webrtc"

export async function getBrowser(proxyIp: string) {
	const path = process.platform === "darwin" ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" : "/usr/bin/google-chrome-stable"
	const browser = await puppeteer.launch({
		executablePath: path,
		headless: true,
		args: get_chrome_flags(proxyIp),
		defaultViewport: {
			width: 1920,
			height: 1080,
		}
	})
	return browser
}

export async function newPage(browser: Browser, username: string, password: string) {
	const page = await browser.newPage()
	console.log("New page created")
	await page.authenticate({ username, password })
	return page
}

export function get_chrome_flags(proxyIp: string) {
	return [
		`--disable-extensions-except=${EXTENSION_PATH}`,
		`--load-extension=${EXTENSION_PATH}`,
		"--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
		`--proxy-server=${proxyIp}`,
		"--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
		"--no-sandbox",
		"--disable-setuid-sandbox",
		"--disabled-gpu",
		"--no-first-run",
	]
}