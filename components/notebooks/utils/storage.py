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

def download_plain_text(filename):
	blob = bucket.blob(f"{filename}-plaintext.txt")
	plaintext = blob.download_as_bytes().decode("utf-8")
	return plaintext

def download_sparse_vectors(filename):
	blob = bucket.blob(f"{filename}-vectors.json")
	vectors = blob.download_as_bytes().decode("utf-8")
	return loads(vectors)

# ************************
# * DOWNLOADING METADATA *
# ************************

REPLACEMENTS = {
	"reinforcement-learning": "reinforcement learning",
	"object-detection": "object detection",
	"speech-recognition": "speech recognition",
	"intent-classification": "intent classification",
	"speaker-diarization": "speaker diarization",
	"coreference-resolution": "coreference resolution",
	"text-classification": "text classification",
	"sentence-embedding": "sentence embedding",
	"question-generation": "question generation",
	"named-entity-recognition": "named entity recognition",
	"multi label text classification": "multi-label text classification",
	"multilabel text classification": "multi-label text classification",
	"slot-filling": "slot filling",
	"few shot action recognition": "few-shot action recognition",
	"continuous-control": "continuous control",
	"open vocabulary semantic segmentation": "open-vocabulary semantic segmentation",
	"class-incremental learning": "class-incremental learning",
	"low resource neural machine translation": "low-resource neural machine translation",
	"token-classification": "token classification",
	"open vocabulary object detection": "open-vocabulary object detection",
	"hand gesture recognition": "hand gesture recognition",
	"weakly supervised temporal action localization": "weakly-supervised temporal action localization",
	"micro expression recognition": "micro-expression recognition",
	"multi future trajectory prediction": "multi-future trajectory prediction",
	"fill-mask": "fill mask",
	"alzheimer's detection": "alzheimer's detection",
	"alzheimer's disease detection": "alzheimer's detection",
	"1 image, 2*2 stitchi": "1 image, 2*2 stitching",
	"multi view detection": "multi-view detection",
	"inverse-tone-mapping": "inverse tone mapping",
	"text based person retrieval": "text-based person retrieval",
	"text to speech": "text-to-speech",
	"reranking": "re-ranking",
	"passage reranking": "passage re-ranking",
	"multimodal recommendation": "multi-modal recommendation",
	"hand-gesture recognition": "hand gesture recognition",
	"multiview learning": "multi-view learning",
	"multi-label-classification": "multi-label classification",
	"lip reading": "lipreading",
	"weakly supervised semantic segmentation": "weakly-supervised semantic segmentation",
	"zeroshot video question answer": "zero-shot video question answering",
	"few-shot-ner": "few-shot ner",
	"multi-media recommendation": "multimedia recommendation",
	"math word problem solvingω": "math word problem solving",
	"full reference image quality assessment": "full-reference image quality assessment",
	"valid": None,
	"all": None,
	"model": None,
	"sentence": None,
	"attribute": None,
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
		task = task.lower()
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
			replacements.append(task)

	metadata["tasks"] = replacements

	return metadata

def download_keywords(filename):
	blob = bucket.blob(f"{filename}-keywords.json")
	keywords = blob.download_as_bytes().decode("utf-8")
	return loads(keywords)

# *******************
# * UPLOADING FILES *
# *******************

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