"""
ingest.py
Reads reviews from data/reviews.json, generates Gemini embeddings,
and indexes everything into Elasticsearch.
"""

import os
import json
import time
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, helpers
from google import genai
import google.genai.types as types

load_dotenv()

INDEX_NAME = "campus_reviews"
DATA_PATHS = ["data/reviews.json"]
BATCH_SIZE = 20  # embeddings per API call
EMBEDDING_MODEL = "models/gemini-embedding-2"


def get_es_client():
    return Elasticsearch(
        os.getenv("ELASTICSEARCH_URL"),
        api_key=os.getenv("ELASTICSEARCH_API_KEY"),
    )


def get_gemini_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def generate_embeddings(client, texts):
    """Generate embeddings for a batch of texts using Gemini."""
    contents = [types.Content(parts=[types.Part(text=text)]) for text in texts]
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=contents,
    )
    return [e.values for e in result.embeddings]


def build_doc_text(review):
    """Build a rich text string for embedding — combines key fields."""
    parts = [
        f"Professor: {review.get('professor_name', '')}",
        f"Department: {review.get('department', '')}",
        f"School: {review.get('school', '')}",
        f"Course: {review.get('course', '')}",
        f"Review: {review.get('comment', '')}",
    ]
    return " | ".join(p for p in parts if p.split(": ", 1)[1])


def ingest():
    print("Loading reviews from all sources...")
    reviews = []
    for path in DATA_PATHS:
        if not os.path.exists(path):
            print(f"  Skipping {path} — file not found")
            continue
        with open(path, "r", encoding="utf-8") as f:
            batch = json.load(f)
        print(f"  {len(batch):5} reviews from {path}")
        reviews.extend(batch)
    print(f"  ─────────────────────────────")
    print(f"  {len(reviews):5} total reviews loaded")

    es = get_es_client()
    gemini = get_gemini_client()

    actions = []
    total = len(reviews)

    for i in range(0, total, BATCH_SIZE):
        batch = reviews[i : i + BATCH_SIZE]
        texts = [build_doc_text(r) for r in batch]

        print(f"  Embedding batch {i//BATCH_SIZE + 1}/{(total + BATCH_SIZE - 1)//BATCH_SIZE}...")
        try:
            embeddings = generate_embeddings(gemini, texts)
        except Exception as e:
            print(f"  Embedding error: {e} — skipping batch")
            embeddings = [None] * len(batch)

        for review, embedding in zip(batch, embeddings):
            doc = {**review}
            if embedding:
                doc["embedding"] = embedding
            actions.append({
                "_index": INDEX_NAME,
                "_source": doc,
            })

        time.sleep(0.5)  # avoid rate limits

    print(f"\nIndexing {len(actions)} documents into Elasticsearch...")
    success, errors = helpers.bulk(es, actions, raise_on_error=False)
    print(f"✅ Indexed {success} documents")
    if errors:
        print(f"⚠️  {len(errors)} errors — check data/ingest_errors.json")
        with open("data/ingest_errors.json", "w") as f:
            json.dump(errors, f, indent=2)


if __name__ == "__main__":
    ingest()
