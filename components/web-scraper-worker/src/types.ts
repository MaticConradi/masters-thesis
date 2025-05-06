export type Result = {
	task: string
	dataset: string
	model: string
	metric: string
	value: string
	rank: number
}

export type PaperMetadata = {
	title: string
	origin: string
	tasks: string[]
	datasets: string[]
	results: Result[]
	methods: string[]
}