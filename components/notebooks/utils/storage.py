from os import path
from json import dumps, loads
from google.cloud import storage

BUCKET_NAME = "mc-mag-temp-ml-papers"

storage = storage.Client()
bucket = storage.bucket(BUCKET_NAME)

# *****************
# * LISTING FILES *
# *****************

def list_unprocessed_pdf_files():
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

def list_pdf_files():
	blobs = bucket.list_blobs()

	files = set()
	keywords = set()

	for blob in blobs:
		name, ext = path.splitext(blob.name)
		if ext.lower() == ".pdf":
			files.add(name)

	return files

def list_mmd_files():
	blobs = bucket.list_blobs()

	files = set()

	for blob in blobs:
		name, ext = path.splitext(blob.name)
		if ext.lower() == ".mmd" and not name.endswith("-corrected"):
			files.add(name)

	return files

def list_processed_mmd_files():
	blobs = bucket.list_blobs()

	files = set()

	for blob in blobs:
		name, ext = path.splitext(blob.name)
		if ext.lower() == ".mmd" and name.endswith("-corrected"):
			files.add(name[:-10])

	return files

def list_keywordless_mmd_files():
	blobs = bucket.list_blobs()

	files = set()
	keywords = set()

	for blob in blobs:
		name, ext = path.splitext(blob.name)
		if ext.lower() == ".mmd" and name.endswith("-corrected"):
			files.add(name[:-10])
		elif ext.lower() == ".json" and name.endswith("-keywords"):
			keywords.add(name[:-9])

	files = files - keywords

	return files

def list_sparse_vector_files():
	blobs = bucket.list_blobs()

	files = set()

	for blob in blobs:
		name, ext = path.splitext(blob.name)
		if ext.lower() == ".json" and name.endswith("-vectors"):
			files.add(name[:-8])

	return files

def list_plaintextless_files():
	blobs = bucket.list_blobs()

	files = set()
	plaintext = set()

	for blob in blobs:
		name, ext = path.splitext(blob.name)
		if ext.lower() == ".mmd" and name.endswith("-corrected"):
			files.add(name[:-10])
		elif ext.lower() == ".txt" and name.endswith("-plaintext"):
			plaintext.add(name[:-10])

	files = files - plaintext

	return files

# *********************
# * DOWNLOADING FILES *
# *********************

def download_mmd_file(filename):
	blob = bucket.blob(f"{filename}.mmd")
	md = blob.download_as_bytes().decode("utf-8")
	return md

def download_processed_mmd_file(filename):
	blob = bucket.blob(f"{filename}-corrected.mmd")
	md = blob.download_as_bytes().decode("utf-8")
	return md

# ************************
# * DOWNLOADING METADATA *
# ************************

REPLACEMENTS = {
	"reinforcement-learning": "Reinforcement Learning",
	"object-detection": "Object Detection",
	"speech-recognition": "Speech Recognition",
	"intent-classification": "Intent Classification",
	"speaker-diarization": "Speaker Diarization",
	"coreference-resolution": "Coreference Resolution",
	"text-classification": "Text Classification",
	"Sentence-Embedding": "Sentence Embedding",
	"Question-Generation": "Question Generation",
	"named-entity-recognition": "Named Entity Recognition",
	"Multi Label Text Classification": "Multi-Label Text Classification",
	"slot-filling": "Slot Filling",
	"Few Shot Action Recognition": "Few-Shot action recognition",
	"continuous-control": "Continuous Control",
	"Open Vocabulary Semantic Segmentation": "Open-Vocabulary Semantic Segmentation",
	"class-incremental learning": "Class Incremental Learning",
	"Low Resource Neural Machine Translation": "Low-Resource Neural Machine Translation",
	"token-classification": "Token Classification",
	"Open Vocabulary Object Detection": "Open-vocabulary object detection",
	"Hand Gesture Recognition": "Hand-Gesture Recognition",
	"Weakly Supervised Temporal Action Localization": "Weakly-supervised Temporal Action Localization",
	"Micro Expression Recognition": "Micro-Expression Recognition",
	"Multi Future Trajectory Prediction": "Multi-future Trajectory Prediction",
	"fill-mask": "Fill Mask",
	"valid": None,
	"All": None,
	"Model": None,
	"Sentence": None,
	"Attribute": None,
}

def download_file_metadata(filename):
	blob = bucket.blob(f"{filename}.pdf")
	blob.patch()
	metadata = blob.metadata

	for key, value in metadata.items():
		metadata[key] = loads(value)

	tasks = metadata["tasks"]
	replacements = []
	for task in tasks:
		if task in REPLACEMENTS:
			replacement = REPLACEMENTS[task]
			if replacement is None:
				# If the replacement is None, we skip this task
				continue
			elif replacement not in tasks:
				# Only add the replacement if it is not already in the tasks
				replacements.append(replacement)
			else:
			# If the replacement is already in the tasks, we skip it
				continue
		else:
			# If the task is not in the replacements, we keep it as is
			replacements.append(task.title())

	metadata["tasks"] = replacements

	return metadata

def download_keywords(filename):
	blob = bucket.blob(f"{filename}-keywords.json")
	keywords = blob.download_as_bytes().decode("utf-8")
	return loads(keywords)

def download_plain_text(filename):
	blob = bucket.blob(f"{filename}-plaintext.txt")
	plaintext = blob.download_as_bytes().decode("utf-8")
	return plaintext

# *******************
# * UPLOADING FILES *
# ****************

def upload_keywords(filename, keywords):
	blob = bucket.blob(f"{filename}-keywords.json")
	blob.upload_from_string(dumps(keywords), content_type="application/json")

def upload_sparse_vectors(filename, vectors):
	blob = bucket.blob(f"{filename}-vectors.json")
	blob.upload_from_string(dumps(vectors), content_type="application/json")

def upload_plaintext(filename, plaintext):
	blob = bucket.blob(f"{filename}-plaintext.txt")
	blob.upload_from_string(plaintext, content_type="text/plain")

# ****************
# * DELETE FILES *
# ****************

def delete_cleaned_mmd(filename):
	blob = bucket.blob(f"{filename}-corrected.mmd")
	try: blob.delete()
	except: pass
	blob = bucket.blob(f"{filename}-keywords.json")
	try: blob.delete()
	except: pass