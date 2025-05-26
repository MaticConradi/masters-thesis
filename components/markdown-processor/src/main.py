from time import time
from os import path, getenv
import tempfile
import shutil
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

		print(f"Downloading {filename}.pdf to {localPdfPath}...")
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
			print("No text found in PDF. Skipping file")
			return

		response = client.responses.create(
			model="gpt-4.1-nano",
			input=f"Inaccurate OCR text with markdown formatting:\n```{mmdContent}```\n\nExtracted unformatted text:\n```{text}```\n\nProvide a corrected version of the markdown text, ensuring that the formatting is preserved and the content is accurate. The output should be in markdown format. Respond with a single code block marked with ```.",
		)
		print("Received response from OpenAI API.")

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
			raise ValueError("No valid start marker found in the response.")

		# Determine the end index of the content, which is at the beginning of the last "```"
		endIndex = response.output_text.rfind("```")

		# Extract and strip if valid start and end positions are found
		if startIndex != -1 and endIndex != -1 and endIndex >= startIndex:
			output = response.output_text[startIndex:endIndex].strip()
		else:
			raise ValueError("Invalid start or end index for content extraction.")

		# Upload the corrected markdown content to GCS
		print("Uploading corrected markdown content to GCS and BigQuery...")
		correctedMmdFilename = f"{filename}-corrected.mmd"
		correctedMmdBlob = bucket.blob(correctedMmdFilename)
		correctedMmdBlob.upload_from_string(output, content_type="text/markdown")

		# Insert the metadata into BigQuery
		# bqRow = {
		# }
		# bigquery.insert_rows_json(table, [bqRow])
		print(f"Uploaded corrected markdown file: {correctedMmdFilename}")

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

	for pdf_filename in processedFiles:
		try:
			process_file(pdf_filename)
		except KeyboardInterrupt:
			break
		except Exception as e:
			print(f"Error processing {pdf_filename}: {e}")

if __name__ == "__main__":
	main()