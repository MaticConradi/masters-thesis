from time import time
from os import path, getenv
import subprocess
import tempfile
import shutil
from flask import Flask, jsonify
from google.cloud import storage

BUCKET_NAME = getenv("ML_PAPERS_BUCKET_NAME")
storageClient = storage.Client()
bucket = storageClient.bucket(BUCKET_NAME)

app = Flask(__name__)

CHUNK_SIZE = 8

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

def process_pdf_file(pdf_filenames, start_time):
	"""
	Downloads a PDF file from GCS, processes it with nougat,
	and uploads the resulting .mmd file back to GCS.

	Args:
		pdf_filename (str): The name of the PDF file in GCS.
		start_time (int): The start time for processing, used for logging.
	"""

	if start_time < time() - 60 * 55:
		raise KeyboardInterrupt("Processing time exceeded 55 minutes")

	if len(pdf_filenames) == 0:
		return

	temporaryDir = tempfile.mkdtemp()
	try:
		localPdfPaths = []

		for pdfFilename in pdf_filenames:
			localPdfPath = path.join(temporaryDir, pdfFilename)

			# Download PDF from GCS
			print(f"Downloading {pdfFilename} to {localPdfPath}...")
			blob = bucket.blob(pdfFilename)
			blob.download_to_filename(localPdfPath)
			localPdfPaths.append(localPdfPath)
			print(f"Downloaded {pdfFilename}")

		# Run nougat command
		# nougat expects the output directory to exist.
		# The output filename will be the same as input but with .mmd
		print(f"Processing {', '.join(pdf_filenames)} with nougat...")
		# The nougat command will create a .mmd file in the temporaryDir
		subprocess.run(
			["nougat", "-o", temporaryDir, "--no-skipping"] + localPdfPaths,
			check=True, # Raises CalledProcessError if command returns non-zero exit code
			capture_output=True # To capture stdout/stderr if needed
		)
		print(f"Finished processing {len(pdf_filenames)} files")

		for pdfFilename in pdf_filenames:
			# Upload the .mmd file
			filename, _ = path.splitext(pdfFilename)
			mmdFilename = f"{filename}.mmd"
			localMmdPath = path.join(temporaryDir, mmdFilename)

			if path.exists(localMmdPath):
				print(f"Uploading {mmdFilename} to GCS bucket {BUCKET_NAME}...")
				mmdBlob = bucket.blob(mmdFilename)
				mmdBlob.upload_from_filename(localMmdPath)
				print(f"Uploaded {mmdFilename}")
			else:
				print(f"Error: Output file {localMmdPath} not found after nougat processing")

	except subprocess.CalledProcessError as e:
		print(f"Error processing {', '.join(pdf_filenames)} with nougat: {e}")
		if e.stdout:
			print(f"Nougat stdout: {e.stdout.decode()}")
		if e.stderr:
			print(f"Nougat stderr: {e.stderr.decode()}")
	except Exception as e:
		print(f"An error occurred while processing {', '.join(pdf_filenames)}: {e}")
	finally:
		# Clean up the temporary directory
		if path.exists(temporaryDir):
			print(f"Cleaning up temporary directory: {temporaryDir}")
			shutil.rmtree(temporaryDir)

def iterate_in_chunks(data, chunk_size):
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]

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
		for filenames in iterate_in_chunks(unprocessedFiles, CHUNK_SIZE):
			try:
				print(f"Starting processing for {', '.join(filenames)}")
				process_pdf_file(filenames, startTime)
				processed_files += filenames
				print(f"Finished processing for {', '.join(filenames)}")
			except KeyboardInterrupt:
				break
			except Exception as e:
				print(f"An error occurred while processing {', '.join(filenames)} in the route: {e}")
				errors.append({"filename": filenames, "error": str(e)})

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