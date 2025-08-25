from os import getenv, mkdir
import sys
import sqlite3
import torch
import numpy as np
import faiss
import threading
from flask import Flask, jsonify, request
from transformers import AutoTokenizer, AutoModelForMaskedLM
from openai import OpenAI
from google.cloud import storage
from traceback import print_exc

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

		results = search_index(query, k)

		response = {
			'results': [
				{
					'document': filename,
					'score': float(score)
				}
				for filename, score in results
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

		results = search_dense_index(query, k)

		response = {
			'results': [
				{
					'document': filename,
					'score': float(score)
				}
				for filename, score in results
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

		# Apply reciprocal rank fusion
		fusedResults = reciprocal_rank_fusion(denseResults, sparseResults, k)

		response = {
			'results': [
				{
					'document': filename,
					'rrf_score': float(score)
				}
				for filename, score in fusedResults
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