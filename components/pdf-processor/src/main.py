from time import time
from os import path, getenv
import subprocess
import tempfile
import shutil
from flask import Flask, request, jsonify
from google.cloud import storage

BUCKET_NAME = getenv("ML_PAPERS_BUCKET_NAME")
storageClient = storage.Client()
bucket = storageClient.bucket(BUCKET_NAME)

app = Flask(__name__)

def list_unprocessed_pdf_files():
	"""
	Lists PDF files in a GCS bucket that do not have a corresponding .mmd file.

	Args:
		bucket_name (str): The name of the GCS bucket.

	Returns:
		list: A list of PDF filenames that do not have a corresponding .mmd file.
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

	unprocessedPdfFiles = pdfFiles - mmdFiles
	result = [f"{name}.pdf" for name in unprocessedPdfFiles]

	return result

def process_pdf_file(pdf_filename: str, start_time: int):
	"""
	Downloads a PDF file from GCS, processes it with nougat,
	and uploads the resulting .mmd file back to GCS.

	Args:
		pdf_filename (str): The name of the PDF file in GCS.
		start_time (int): The start time for processing, used for logging.
	"""

	if start_time < time() - 60 * 55:
		return

	temporaryDir = tempfile.mkdtemp()
	try:
		localPdfPath = path.join(temporaryDir, pdf_filename)

		# Download PDF from GCS
		print(f"Downloading {pdf_filename} to {localPdfPath}...")
		blob = bucket.blob(pdf_filename)
		blob.download_to_filename(localPdfPath)
		print(f"Downloaded {pdf_filename}.")

		# Run nougat command
		# nougat expects the output directory to exist.
		# The output filename will be the same as input but with .mmd
		print(f"Processing {pdf_filename} with nougat...")
		# The nougat command will create a .mmd file in the temporaryDir
		subprocess.run(
			["nougat", localPdfPath, "-o", temporaryDir, "--no-skipping"],
			check=True, # Raises CalledProcessError if command returns non-zero exit code
			capture_output=True # To capture stdout/stderr if needed
		)
		print(f"Finished processing {pdf_filename}.")

		# Upload the .mmd file
		filename, _ = path.splitext(pdf_filename)
		mmdFilename = f"{filename}.mmd"
		localMmdPath = path.join(temporaryDir, mmdFilename)

		if path.exists(localMmdPath):
			print(f"Uploading {mmdFilename} to GCS bucket {BUCKET_NAME}...")
			mmdBlob = bucket.blob(mmdFilename)
			mmdBlob.upload_from_filename(localMmdPath)
			print(f"Uploaded {mmdFilename}.")
		else:
			print(f"Error: Output file {localMmdPath} not found after nougat processing.")

	except subprocess.CalledProcessError as e:
		print(f"Error processing {pdf_filename} with nougat: {e}")
		if e.stdout:
			print(f"Nougat stdout: {e.stdout.decode()}")
		if e.stderr:
			print(f"Nougat stderr: {e.stderr.decode()}")
	except Exception as e:
		print(f"An error occurred while processing {pdf_filename}: {e}")
	finally:
		# Clean up the temporary directory
		if path.exists(temporaryDir):
			print(f"Cleaning up temporary directory: {temporaryDir}")
			shutil.rmtree(temporaryDir)

@app.route("/process", methods=['GET'])
def process_pdfs_route():
	"""
	Flask route to trigger the PDF listing and processing.
	"""
	startTime = time()

	try:

		unprocessedFiles = list_unprocessed_pdf_files()
		if not unprocessedFiles:
			print("No new PDF files to process.")
			return jsonify({"message": "No new PDF files to process."}), 200

		print(f"Found {len(unprocessedFiles)} PDF files to process: {unprocessedFiles}")
		processed_files = []
		errors = []
		for filename in unprocessedFiles:
			try:
				print(f"Starting processing for {filename}")
				process_pdf_file(filename, startTime)
				processed_files.append(filename)
				print(f"Finished processing for {filename}")
			except Exception as e: # Catching exceptions here as well for overall status
				print(f"An error occurred while processing {filename} in the route: {e}")
				errors.append({"filename": filename, "error": str(e)})

		if errors:
			return jsonify({
				"message": "Completed processing with some errors.",
				"processed_files": processed_files,
				"errors": errors
			}), 207 # Multi-Status

		return jsonify({
			"message": f"Successfully processed {len(processed_files)} files.",
			"processed_files": processed_files
		}), 200

	except Exception as e:
		print(f"An unexpected error occurred in /process route: {e}")
		return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

if __name__ == "__main__":
	port = int(getenv("PORT", 8080))
	app.run(debug=True, host='0.0.0.0', port=port)