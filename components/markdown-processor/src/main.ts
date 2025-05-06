import { GoogleGenAI } from '@google/genai';
import { Storage } from '@google-cloud/storage';
import pdf from 'pdf-parse';

const storage = new Storage();
const bucket = storage.bucket(process.env.ML_PAPERS_BUCKET_NAME!);

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY! });

async function listFiles() {
	const [files] = await bucket.getFiles();

	const filenames = [];
	for (const file of files) {
		if (file.name.endsWith('.mmd')) {
			const filename = file.name.replace('.mmd', '');
			filenames.push(filename);
		}
	}

	return filenames;
}

async function processFile(filename: string) {
	const pdfFileObject = bucket.file(`${filename}.pdf`);
	const mmdFileObject = bucket.file(`${filename}.mmd`);

	const [pdfMetadata] = await pdfFileObject.getMetadata();

	const pdfFile = await pdfFileObject.download();
	const mmdFile = await mmdFileObject.download();

	const pdfData = await pdf(pdfFile[0]);
	const mmdContent = mmdFile[0].toString('utf-8');

	const response = await ai.models.generateContent({
		model: "gemini-2.5-pro-preview-05-06",
		contents: `Inaccurate OCR text with markdown formatting:\n\`\`\`${mmdContent}\`\`\`\n\nExtracted raw text:\n\`\`\`${pdfData.text}\`\`\`\n\nPlease provide a corrected version of the markdown text, ensuring that the formatting is preserved and the content is accurate. The output should be in markdown format.`,
		config: {
			thinkingConfig: {
				thinkingBudget: 0,
				includeThoughts: false,
			}
		}
	});

	console.log(`Response for ${filename}:\n`, response.text);
}

async function main() {
	const files = await listFiles();
	for (const file of files) {
		console.log(`Processing ${file}`);
		await processFile(file);
		break;
	}
	console.log('All files processed');
}

main()

process.on('SIGINT', async () => {
	console.log('Shutting down...');
	process.exit(0);
});