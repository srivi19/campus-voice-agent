"""
agent.py
Gemini-powered agent that answers natural language questions
about student reviews stored in Elasticsearch.
"""

import os
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from google import genai

load_dotenv()

INDEX_NAME = "campus_reviews"
EMBEDDING_MODEL = "models/gemini-embedding-2"


def get_es_client():
    return Elasticsearch(
        os.getenv("ELASTICSEARCH_URL"),
        api_key=os.getenv("ELASTICSEARCH_API_KEY"),
    )


def get_gemini_client():
    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def embed_question(client, question):
    """Embed the user's question for semantic search."""
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=[question],
    )
    return result.embeddings[0].values


def search_reviews(es, question_embedding, school_filter=None, department_filter=None, top_k=20):
    """Hybrid search: vector similarity + optional keyword filters."""
    must_filters = []
    if school_filter:
        must_filters.append({"term": {"school_tag": school_filter}})
    if department_filter:
        must_filters.append({"match": {"department": department_filter}})

    query = {
        "knn": {
            "field": "embedding",
            "query_vector": question_embedding,
            "k": top_k,
            "num_candidates": 100,
            "filter": {"bool": {"must": must_filters}} if must_filters else None,
        },
        "_source": {
            "excludes": ["embedding"]  # don't return the big vector
        },
        "size": top_k,
    }

    # Remove None filter
    if not must_filters:
        del query["knn"]["filter"]

    resp = es.search(index=INDEX_NAME, body=query)
    return [hit["_source"] for hit in resp["hits"]["hits"]]


def build_prompt(question, reviews):
    """Build the synthesis prompt for Gemini."""
    review_text = ""
    for i, r in enumerate(reviews, 1):
        review_text += (
            f"\n[{i}] School: {r.get('school')} | "
            f"Professor: {r.get('professor_name')} | "
            f"Dept: {r.get('department')} | "
            f"Course: {r.get('course')} | "
            f"Rating: {r.get('helpful_rating')}/5\n"
            f"    \"{r.get('comment', '')}\"\n"
        )

    return f"""You are CampusVoice, an AI analyst helping administrators, counselors, and students understand what students really think about universities based on real reviews.

Answer the following question using ONLY the provided student reviews. Be specific, cite numbers when possible, quote real reviews (keep quotes short), and identify patterns. If comparing two schools, clearly distinguish them.

QUESTION: {question}

STUDENT REVIEWS:
{review_text}

Provide a clear, structured answer. Start directly with your findings — no need to say "Based on the reviews..." Just answer."""


def ask(question, school_filter=None, department_filter=None):
    """Main entry point: ask a question, get an answer."""
    es = get_es_client()
    gemini = get_gemini_client()

    # Embed the question
    question_embedding = embed_question(gemini, question)

    # Search Elasticsearch
    reviews = search_reviews(es, question_embedding, school_filter, department_filter)

    if not reviews:
        return "No relevant reviews found. Try broadening your question."

    # Build prompt and get Gemini answer
    prompt = build_prompt(question, reviews)
    response = gemini.models.generate_content(
        model="models/gemini-3.5-flash",
        contents=prompt,
    )

    return response.text


if __name__ == "__main__":
    # Quick test
    answer = ask("What do students think about professors at UTK?", school_filter="utk")
    print(answer)
