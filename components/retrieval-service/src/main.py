from os import getenv
import sqlite3
import torch
import numpy as np
import faiss
from flask import Flask, jsonify, request
from transformers import AutoTokenizer, AutoModelForMaskedLM
from openai import OpenAI
from google.cloud import storage

BUCKET_NAME = getenv("ML_PAPERS_BUCKET_NAME")
print(BUCKET_NAME)
storageClient = storage.Client()
bucket = storageClient.bucket(BUCKET_NAME)

# Download and load sparse index
SPARSE_INDEX_PATH = "./sparse_index.db"
bucket.blob("index/sparse_index.db").download_to_filename(SPARSE_INDEX_PATH)
conn = sqlite3.connect(SPARSE_INDEX_PATH, check_same_thread=False)
cursor = conn.cursor()

# Global model initialization
MODEL_NAME = "naver/splade-cocondenser-ensembledistil"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForMaskedLM.from_pretrained(MODEL_NAME, device_map="auto")
model.eval()

# OpenAI client for dense search
client = OpenAI()

# Load dense index and create document mapping
cursor.execute("SELECT id, filename FROM documents")
documents = cursor.fetchall()
indexDocumentMap = {row[0]: row[1] for row in documents}

# Download and load dense index
DENSE_INDEX_PATH = "./dense_index.faiss"
bucket.blob("index/dense_index.faiss").download_to_filename(DENSE_INDEX_PATH)
dense_index = faiss.read_index(DENSE_INDEX_PATH)

app = Flask(__name__)

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

	distances, identifiers = dense_index.search(embedding, k * 4)

	documentIds = []
	results = []
	for i in range(identifiers.shape[1]):
		document = indexDocumentMap[identifiers[0, i]]
		if document not in documentIds:
			documentIds.append(document)
			results.append((document, float(distances[0, i])))

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
	try:
		data = request.get_json()

		if not data or 'query' not in data:
			return jsonify({'error': 'Query parameter is required'}), 400

		query = data['query']
		k = data.get('k', 5)  # Default to top 5 results

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
		return jsonify({'error': 'Internal server error'}), 500

@app.route('/search/dense', methods=['POST'])
def search_dense():
	try:
		data = request.get_json()

		if not data or 'query' not in data:
			return jsonify({'error': 'Query parameter is required'}), 400

		query = data['query']
		k = data.get('k', 5)  # Default to top 5 results

		if not query.strip():
			return jsonify({'error': 'Query cannot be empty'}), 400

		results = search_dense_index(query, k)

		response = {
			'results': [
				{
					'document': filename,
					'distance': float(distance)
				}
				for filename, distance in results
			]
		}

		return jsonify(response)

	except Exception as e:
		return jsonify({'error': 'Internal server error'}), 500

@app.route('/search/hybrid', methods=['POST'])
def search_hybrid():
	try:
		data = request.get_json()

		if not data or 'query' not in data:
			return jsonify({'error': 'Query parameter is required'}), 400

		query = data['query']
		k = data.get('k', 5)  # Default to top 5 results

		if not query.strip():
			return jsonify({'error': 'Query cannot be empty'}), 400

		# Get results from both search methods with higher k for better fusion
		fusion_k = max(k * 4, 50)  # Use larger k for fusion input

		sparse_results = search_index(query, fusion_k)
		dense_results = search_dense_index(query, fusion_k)

		# Apply reciprocal rank fusion
		fused_results = reciprocal_rank_fusion(dense_results, sparse_results, k)

		response = {
			'results': [
				{
					'document': filename,
					'rrf_score': float(score)
				}
				for filename, score in fused_results
			]
		}

		return jsonify(response)

	except ValueError as e:
		return jsonify({'error': str(e)}), 400
	except Exception as e:
		return jsonify({'error': 'Internal server error'}), 500

CHUNK_SIZE = 8

if __name__ == "__main__":
	port = int(getenv("PORT", 8080))
	app.run(debug=True, host='0.0.0.0', port=port)