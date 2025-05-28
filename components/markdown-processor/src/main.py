from time import time
from os import path, getenv
import tempfile
import shutil
from multiprocessing.pool import ThreadPool
from PyPDF2 import PdfReader
from openai import OpenAI
from google.cloud import storage
from google.cloud import bigquery

BUCKET_NAME = getenv("ML_PAPERS_BUCKET_NAME")
storage = storage.Client()
bucket = storage.bucket(BUCKET_NAME)

bigquery = bigquery.Client()
dataset = bigquery.dataset("mc_magistrska")
table = dataset.table("articles")

client = OpenAI()

def list_processed_pdf_files():
	"""
	Lists PDF files in a GCS bucket that have a corresponding .mmd file.

	Returns:
		list: A list of PDF filenames that have a corresponding .mmd file.
	"""

	blobs = bucket.list_blobs()

	pdfFiles = set()
	mmdFiles = set()
	correctedMmdFiles = set()

	for blob in blobs:
		name, ext = path.splitext(blob.name)
		if ext.lower() == ".pdf":
			pdfFiles.add(name)
		elif ext.lower() == ".mmd" and name.endswith("-corrected"):
			correctedMmdFiles.add(name)
		elif ext.lower() == ".mmd":
			mmdFiles.add(name)

	result = pdfFiles.intersection(mmdFiles).difference(correctedMmdFiles)

	return result

def process_file(filename: str):
	temporaryDir = tempfile.mkdtemp()

	try:
		localPdfPath = path.join(temporaryDir, f"{filename}.pdf")

		pdfBlob = bucket.blob(f"{filename}.pdf")
		pdfBlob.download_to_filename(localPdfPath)
		pdfMetadata = pdfBlob.metadata
		print(f"Downloaded {filename}.pdf")

		mmdBlob = bucket.blob(f"{filename}.mmd")
		mmdContent = mmdBlob.download_as_bytes().decode('utf-8')

		pdfData = PdfReader(localPdfPath)
		text = ""
		for page in pdfData.pages:
			text += page.extract_text()

		if text == "":
			print(f"No text found in {filename}, skipping file")
			return

		response = client.responses.create(
			model="gpt-4.1-nano",
			instructions="Combine the two provided texts, ensuring that the formatting is preserved and the content is accurate. The output should be in markdown format. Provide the complete text without any placeholders or references to the original content for the sake of shortening the response; always provide the full content, all within a single code block marked with ``` at the start and at the end of the block. Do not add any additional formatting beyond what is necessary to preserve the original structure and content.",
			input=f"Inaccurate OCR text with markdown formatting:\n```{mmdContent}```\n\nUnformatted text:\n```{text}```",
		)

		# Determine the start index of the content, after the first "```markdown" or "```"
		firstMarkerMarkdownIndex = response.output_text.find("```markdown")
		firstMarkerPlainIndex = response.output_text.find("```")

		startIndex = -1
		# Check if "```markdown" is present and is the first relevant marker
		if firstMarkerMarkdownIndex != -1 and (firstMarkerPlainIndex == -1 or firstMarkerMarkdownIndex <= firstMarkerPlainIndex):
			startIndex = firstMarkerMarkdownIndex + len("```markdown")
		# Else, check if "```" is present and is the first relevant marker
		elif firstMarkerPlainIndex != -1:
			startIndex = firstMarkerPlainIndex + len("```")
		else:
			raise ValueError(f"No valid start marker found in the response for {filename}")

		# Determine the end index of the content, which is at the beginning of the last "```"
		endIndex = response.output_text.rfind("```")

		# Extract and strip if valid start and end positions are found
		if startIndex != -1 and endIndex != -1 and endIndex >= startIndex:
			output = response.output_text[startIndex:endIndex].strip()
		else:
			raise ValueError(f"Invalid start or end index for content extraction from {filename}: startIndex={startIndex}, endIndex={endIndex}")

		# Upload the corrected markdown content to GCS
		correctedMmdFilename = f"{filename}-corrected.mmd"
		correctedMmdBlob = bucket.blob(correctedMmdFilename)
		correctedMmdBlob.upload_from_string(output, content_type="text/markdown")

		# Insert the metadata into BigQuery
		# bqRow = {
		# }
		# bigquery.insert_rows_json(table, [bqRow])
		print(f"Uploaded corrected markdown file for {filename}")

	except Exception as e:
		print(f"An error occurred while processing {filename}: {e}")
	finally:
		# Clean up the temporary directory
		if path.exists(temporaryDir):
			print(f"Cleaning up temporary directory: {temporaryDir}")
			shutil.rmtree(temporaryDir)

def main():
	"""
	Main function to process PDF files in a GCS bucket.
	"""
	processedFiles = list_processed_pdf_files()
	pool = ThreadPool(processes=32)

	for pdf_filename in processedFiles:
		pool.apply_async(process_file, args=(pdf_filename,))

	pool.close()
	pool.join()

if __name__ == "__main__":
	main()