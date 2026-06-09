"""
ingest_cc.py
Indexes data/cc_posts.json into Elasticsearch without embeddings.
The CampusVoice agent uses BM25 keyword search — embeddings are not queried,
so skipping them is safe and fast.

Usage:
    python ingest_cc.py
"""

import os
import json
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, helpers

load_dotenv()

INDEX_NAME = "campus_reviews"
DATA_PATH  = "data/cc_posts.json"


def main():
    if not os.path.exists(DATA_PATH):
        print(f"File not found: {DATA_PATH}")
        return

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        posts = json.load(f)
    print(f"Loaded {len(posts)} College Confidential posts")

    es = Elasticsearch(
        os.getenv("ELASTICSEARCH_URL"),
        api_key=os.getenv("ELASTICSEARCH_API_KEY"),
    )

    actions = [
        {"_index": INDEX_NAME, "_source": post}
        for post in posts
    ]

    print(f"Indexing {len(actions)} documents...")
    success, errors = helpers.bulk(es, actions, raise_on_error=False, chunk_size=500)
    print(f"✅ Indexed {success} documents")
    if errors:
        print(f"⚠️  {len(errors)} errors")
        with open("data/ingest_cc_errors.json", "w") as f:
            json.dump(errors, f, indent=2)


if __name__ == "__main__":
    main()
