export type Result = {
	task: string
	dataset: string
	model: string
	metric: string
	value: string
	rank: number
}

export type PaperMetadata = {
	tasks: string[],
	datasets: string[],
	results: Result[],
	methods: string[]
}