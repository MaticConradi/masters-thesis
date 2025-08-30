from os import getenv, mkdir
import sys
import sqlite3
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import torch
import numpy as np
import faiss
import threading
from flask import Flask, jsonify, request
from transformers import AutoTokenizer, AutoModelForMaskedLM
from openai import OpenAI
from google.cloud import storage
from traceback import print_exc
from data_types import Results

BUCKET_NAME = getenv("ML_PAPERS_BUCKET_NAME")
storageClient = storage.Client()
bucket = storageClient.bucket(BUCKET_NAME)

# OpenAI client for dense search
client = OpenAI()

# Global variables for indices and models
conn = None
cursor = None
tokenizer = None
model = None
denseIndex = None
indexDocumentMap = None
serviceReady = False

def download_resources():
	global conn, cursor, tokenizer, model, denseIndex, indexDocumentMap, serviceReady

	try:
		# Download and load sparse index
		SPARSE_INDEX_PATH = "sparse_index.db"
		print(f"Downloading {SPARSE_INDEX_PATH}")
		bucket.blob(f"Index/{SPARSE_INDEX_PATH}").download_to_filename(SPARSE_INDEX_PATH)
		print(f"Loaded {SPARSE_INDEX_PATH}")
		conn = sqlite3.connect(f"./{SPARSE_INDEX_PATH}", check_same_thread=False)
		cursor = conn.cursor()

		# Global model initialization
		MODEL_NAME = "splade-cocondenser-ensembledistil"
		blobs = bucket.list_blobs(prefix=f"Models/{MODEL_NAME}")
		mkdir(f"./{MODEL_NAME}")
		for blob in blobs:
			filepath = f"./{MODEL_NAME}/{blob.name.split('/')[-1]}"
			print(f"Downloading {filepath}")
			blob.download_to_filename(filepath)
			print(f"Loaded {filepath}")
		tokenizer = AutoTokenizer.from_pretrained(f"./{MODEL_NAME}")
		model = AutoModelForMaskedLM.from_pretrained(f"./{MODEL_NAME}", device_map="auto")
		model.eval()

		# Download and load dense index
		DENSE_INDEX_PATH = "dense_index.faiss"
		print(f"Downloading {DENSE_INDEX_PATH}")
		bucket.blob(f"Index/{DENSE_INDEX_PATH}").download_to_filename(DENSE_INDEX_PATH)
		print(f"Loaded {DENSE_INDEX_PATH}")
		denseIndex = faiss.read_index(f"./{DENSE_INDEX_PATH}")

		# Load dense index and create document mapping
		cursor.execute("SELECT id, filename FROM documents")
		documents = cursor.fetchall()
		indexDocumentMap = {row[0]: row[1] for row in documents}

		print("All resources downloaded and loaded successfully")
		serviceReady = True

	except Exception as e:
		print(f"Error downloading resources: {e}")
		sys.exit(1)

# Start download in background thread
downloadThread = threading.Thread(target=download_resources, daemon=True)
downloadThread.start()

app = Flask(__name__)

def check_service_ready():
	"""Check if service is ready, return 503 if not"""
	if not serviceReady:
		return jsonify({'error': 'Service is starting, please try again later'}), 503
	return None

def get_url_for(filename):
	blob = bucket.blob(f"{filename}.pdf")
	expires_at = datetime.utcnow() + timedelta(hours=1)
	return blob.generate_signed_url(version="v2", expiration=expires_at)

def download_processed_mmd_file(filename):
	blob = bucket.blob(f"{filename}-corrected.mmd")
	md = blob.download_as_bytes().decode("utf-8")
	return md

def extract_results_from(sample):
	try:
		response = client.responses.parse(
			model="gpt-5-mini",
			reasoning={"effort": "minimal"},
			text={"verbosity": "low"},
			input=[
				{
					"role": "system",
					"content": "You are an expert at structured data extraction. You will be given unstructured text from a research paper and should extract the paper's results into the given structure. Extract an array of results mentioned in the text (one or many). Each result's struct fields should contain minimal information and strictly adhere to the type."
				},
				{
					"role": "user",
					"content": sample
				}
			],
			text_format=Results
		)
		output = response.output_parsed.results
	except Exception as e:
		print(e)
		sleep(5)
		return extract_results_from(inputs)

	if len(output) == 0:
		return None

	results = []
	for result in output:
		results.append({
			"task": result.task,
			"model_name": result.model_name,
			"model_architecture": result.model_architecture,
			"parameter_count": result.parameter_count,
			"metric": result.metric,
			"metric_higher_is_better": result.metric_higher_is_better,
			"value": result.value,
			"value_error": result.value_error,
			"dataset": result.dataset,
			"dataset_version": result.dataset_version,
			"dataset_split": result.dataset_split,
			"inference_time": result.inference_time,
			"inference_time_unit": result.inference_time_unit,
			"inference_device_class": result.inference_device_class
		})

	return results

def extract_results(filenames):
	with ThreadPoolExecutor() as executor:
		texts = list(executor.map(download_processed_mmd_file, filenames))
		results = list(executor.map(extract_results_from, texts))
		return results

def search_index(query, k):
	tokens = tokenizer(query, return_tensors='pt', padding=False, truncation=False)
	if tokens['input_ids'].shape[1] > 512:
		raise ValueError("Input text is too long")

	tokens = {k: v.to(model.device) for k, v in tokens.items()}

	with torch.no_grad():
		outputs = model(**tokens)

	vector = torch.max(
		torch.log(1 + torch.relu(outputs.logits)) * tokens['attention_mask'].unsqueeze(-1),
		dim=1
	)[0].squeeze()

	indices = vector.nonzero().squeeze().cpu().tolist()
	if not isinstance(indices, list):
		indices = [indices]

	if len(indices) == 0:
		return []

	weights = vector[indices].cpu().tolist()

	params = []
	for idx, score in zip(indices, weights):
		params.extend([int(idx), float(score)])
	params.append(k)

	values_placeholders = ', '.join(['(?,?)'] * len(indices))

	sql_query = f'''
		WITH query_terms(term, score) AS (
			VALUES {values_placeholders}
		)
		SELECT
			d.filename AS document,
			SUM(idx.score * q.score) AS total_score
		FROM
			inverted_index AS idx
		JOIN
			query_terms AS q ON idx.term = q.term
		JOIN
			documents AS d ON idx.document_id = d.id
		GROUP BY
			idx.document_id, d.filename
		ORDER BY
			total_score DESC
		LIMIT ?
	'''

	cursor.execute(sql_query, params)
	return cursor.fetchall()

def search_dense_index(query, k):
	response = client.embeddings.create(
		input=query,
		model="text-embedding-3-large"
	)
	embedding = np.array(response.data[0].embedding, dtype=np.float32).reshape(1, -1)

	distances, identifiers = denseIndex.search(embedding, k * 4)

	documentIds = []
	results = []
	for i in range(identifiers.shape[1]):
		document = indexDocumentMap[identifiers[0, i]]
		if document not in documentIds:
			documentIds.append(document)
			results.append((document, float(1 / (distances[0, i] + 0.00000001))))

	return results[:k]

def reciprocal_rank_fusion(dense_results, sparse_results, k):
	combinedDocumentIds = set(d for d, _ in dense_results).union(set(d for d, _ in sparse_results))

	fusedScores = {}
	for documentId in combinedDocumentIds:
		rrfScore = 0.0
		for i, (d, _) in enumerate(dense_results):
			if documentId == d:
				rank = i + 1
				rrfScore += 1.0 / rank
				break
		for i, (d, _) in enumerate(sparse_results):
			if documentId == d:
				rank = i + 1
				rrfScore += 1.0 / rank
				break
		fusedScores[documentId] = rrfScore

	fusedScores = sorted(fusedScores.items(), key=lambda x: x[1], reverse=True)[:k]

	return fusedScores

@app.route('/search/sparse', methods=['POST'])
def search():
	# Check if service is ready
	readyCheck = check_service_ready()
	if readyCheck:
		return readyCheck

	try:
		data = request.get_json()

		if not data or 'query' not in data:
			return jsonify({'error': 'Query parameter is required'}), 400

		query = data['query']
		k = data.get('k', 20)  # Default to top 20 results

		if not query.strip():
			return jsonify({'error': 'Query cannot be empty'}), 400

		searchResults = search_index(query, k)
		extractedData = extract_results([r[0] for r in searchResults])

		response = {
			'results': [
				{
					'document_id': filename,
					'score': float(score),
					# 'document_url': get_url_for(filename),
					'extracted_data': results
				}
				for (filename, score), results in zip(searchResults, extractedData)
			]
		}

		return jsonify(response)

	except ValueError as e:
		return jsonify({'error': str(e)}), 400
	except Exception as e:
		print_exc()
		return jsonify({'error': 'Internal server error'}), 500

@app.route('/search/dense', methods=['POST'])
def search_dense():
	# Check if service is ready
	readyCheck = check_service_ready()
	if readyCheck:
		return readyCheck

	try:
		data = request.get_json()

		if not data or 'query' not in data:
			return jsonify({'error': 'Query parameter is required'}), 400

		query = data['query']
		k = data.get('k', 20)  # Default to top 20 results

		if not query.strip():
			return jsonify({'error': 'Query cannot be empty'}), 400

		searchResults = search_dense_index(query, k)
		extractedData = extract_results([r[0] for r in searchResults])

		response = {
			'results': [
				{
					'document_id': filename,
					# 'document_url': get_url_for(filename),
					'score': float(score),
					'extracted_data': results
				}
				for (filename, score), results in zip(searchResults, extractedData)
			]
		}

		return jsonify(response)

	except Exception as e:
		print_exc()
		return jsonify({'error': 'Internal server error'}), 500

@app.route('/search/hybrid', methods=['POST'])
def search_hybrid():
	# Check if service is ready
	readyCheck = check_service_ready()
	if readyCheck:
		return readyCheck

	try:
		data = request.get_json()

		if not data or 'query' not in data:
			return jsonify({'error': 'Query parameter is required'}), 400

		query = data['query']
		k = data.get('k', 20)  # Default to top 20 results

		if not query.strip():
			return jsonify({'error': 'Query cannot be empty'}), 400

		fusionK = max(k * 4, 50)

		sparseResults = search_index(query, fusionK)
		denseResults = search_dense_index(query, fusionK)

		searchResults = reciprocal_rank_fusion(denseResults, sparseResults, k)
		extractedData = extract_results([r[0] for r in searchResults])

		response = {
			'results': [
				{
					'document_id': filename,
					'score': float(score),
					# 'document_url': get_url_for(filename),
					'extracted_data': results
				}
				for (filename, score), results in zip(searchResults, extractedData)
			]
		}

		return jsonify(response)

	except ValueError as e:
		return jsonify({'error': str(e)}), 400
	except Exception as e:
		print_exc()
		return jsonify({'error': 'Internal server error'}), 500

if __name__ == "__main__":
	port = int(getenv("PORT", 8080))
	app.run(host='0.0.0.0', port=port)