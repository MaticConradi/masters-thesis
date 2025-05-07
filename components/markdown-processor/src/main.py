from time import time
from os import path, getenv
import tempfile
import shutil
from PyPDF2 import PdfReader
from google import genai
from google.cloud import storage

BUCKET_NAME = getenv("ML_PAPERS_BUCKET_NAME")
storageClient = storage.Client()
bucket = storageClient.bucket(BUCKET_NAME)

client = genai.Client(api_key=getenv("GEMINI_API_KEY"))

def list_processed_pdf_files():
	"""
	Lists PDF files in a GCS bucket that have a corresponding .mmd file.

	Returns:
		list: A list of PDF filenames that have a corresponding .mmd file.
	"""

	blobs = bucket.list_blobs()

	pdfFiles = set()
	mmdFiles = set()

	for blob in blobs:
		name, ext = path.splitext(blob.name)
		if ext.lower() == ".pdf":
			pdfFiles.add(name)
		elif ext.lower() == ".mmd":
			mmdFiles.add(name)

	result = pdfFiles.intersection(mmdFiles)

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

		response = client.models.generate_content(
			model='gemini-2.5-pro-preview-05-06',
			contents=f"Inaccurate OCR text with markdown formatting:\n```{mmdContent}```\n\nExtracted unformatted text:\n```{text}```\n\nProvide a corrected version of the markdown text, ensuring that the formatting is preserved and the content is accurate. The output should be in markdown format."
		)
		print(response.text)

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

	shutil.rmtree(temporaryDir)

if __name__ == "__main__":
	main()