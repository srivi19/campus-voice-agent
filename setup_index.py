"""
setup_index.py
Creates the Elasticsearch index with the right mappings for campus voice data.
Run this once before ingesting data.
"""

import os
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

load_dotenv()

INDEX_NAME = "campus_reviews"

MAPPINGS = {
    "mappings": {
        "properties": {
            "source":               {"type": "keyword"},
            "school":               {"type": "keyword"},
            "school_tag":           {"type": "keyword"},
            "professor_name":       {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "department":           {"type": "keyword"},
            "course":               {"type": "keyword"},
            "comment":              {"type": "text"},
            "category":             {"type": "keyword"},
            "avg_rating":           {"type": "float"},
            "avg_difficulty":       {"type": "float"},
            "would_take_again_pct": {"type": "float"},
            "helpful_rating":       {"type": "integer"},
            "clarity_rating":       {"type": "integer"},
            "difficulty_rating":    {"type": "integer"},
            "would_take_again":     {"type": "integer"},
            "grade":                {"type": "keyword"},
            "date":                 {"type": "keyword"},
            "embedding":            {"type": "dense_vector", "dims": 3072, "index": True, "similarity": "cosine"},
        }
    },
    # Serverless Elasticsearch does not allow explicit replica settings.
    # Keep settings minimal so the index can be created successfully.
}


def get_client():
    return Elasticsearch(
        os.getenv("ELASTICSEARCH_URL"),
        api_key=os.getenv("ELASTICSEARCH_API_KEY"),
    )


def setup():
    es = get_client()

    if es.indices.exists(index=INDEX_NAME):
        print(f"Index '{INDEX_NAME}' already exists. Deleting and recreating...")
        es.indices.delete(index=INDEX_NAME)

    es.indices.create(index=INDEX_NAME, body=MAPPINGS)
    print(f"✅ Index '{INDEX_NAME}' created successfully")


if __name__ == "__main__":
    setup()
