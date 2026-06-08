"""
collect_rmp_missing.py
Collects RMP reviews for the 5 schools missing from Elasticsearch.
Appends to data/reviews.json (does NOT overwrite UTK/Vanderbilt).
Has retry logic and slower rate limiting to avoid blocks.
"""

import requests
import json
import time
import os
import random

RMP_URL = "https://www.ratemyprofessors.com/graphql"
HEADERS = {
    "Authorization": "Basic dGVzdDp0ZXN0",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.ratemyprofessors.com/",
    "Origin": "https://www.ratemyprofessors.com",
}

# Only the 5 schools missing from Elasticsearch
MISSING_SCHOOLS = {
    "Georgia Institute of Technology": "gatech",
    "University of Florida": "uf",
    "University of Michigan": "umich",
    "University of California Los Angeles": "ucla",
    "Duke University": "duke",
}

DATA_PATH = "data/reviews.json"


def post_with_retry(payload, max_attempts=4):
    """POST to RMP GraphQL with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            resp = requests.post(RMP_URL, headers=HEADERS, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if "errors" in data:
                print(f"    GraphQL errors: {data['errors']}")
                return None
            return data
        except Exception as e:
            wait = 2 ** attempt + random.uniform(0.5, 1.5)
            print(f"    Attempt {attempt+1} failed: {e} — retrying in {wait:.1f}s")
            time.sleep(wait)
    return None


def get_school_id(school_name):
    query = """
    query NewSearchSchoolsQuery($query: SchoolSearchQuery!) {
      newSearch {
        schools(query: $query) {
          edges { node { id name city state } }
        }
      }
    }
    """
    data = post_with_retry({"query": query, "variables": {"query": {"text": school_name}}})
    if not data:
        return None
    edges = data["data"]["newSearch"]["schools"]["edges"]
    if not edges:
        print(f"  ⚠ School not found: {school_name}")
        return None
    node = edges[0]["node"]
    print(f"  ✓ Found: {node['name']} ({node['city']}, {node['state']}) → ID: {node['id']}")
    return node["id"]


def get_professors(school_id):
    query = """
    query TeacherSearchResultsPageQuery($query: TeacherSearchQuery!) {
      search: newSearch {
        teachers(query: $query, first: 200) {
          edges {
            node {
              id firstName lastName department
              avgRating avgDifficulty numRatings wouldTakeAgainPercent
            }
          }
        }
      }
    }
    """
    data = post_with_retry({
        "query": query,
        "variables": {"query": {"text": "", "schoolID": school_id}},
    })
    if not data:
        return []
    edges = data["data"]["search"]["teachers"]["edges"]
    profs = [e["node"] for e in edges if e["node"].get("numRatings", 0) > 0]
    # Sort by numRatings desc so we get the most-reviewed professors first
    profs.sort(key=lambda p: p.get("numRatings", 0), reverse=True)
    print(f"  Found {len(profs)} professors with ratings")
    return profs


def get_ratings(professor_id, max_ratings=20):
    query = """
    query RatingsListQuery($id: ID!, $count: Int) {
      node(id: $id) {
        ... on Teacher {
          ratings(first: $count) {
            edges {
              node {
                comment class date
                helpfulRating clarityRating difficultyRating
                wouldTakeAgain grade
              }
            }
          }
        }
      }
    }
    """
    data = post_with_retry({
        "query": query,
        "variables": {"id": professor_id, "count": max_ratings},
    })
    if not data:
        return []
    try:
        edges = data["data"]["node"]["ratings"]["edges"]
        return [e["node"] for e in edges if e["node"].get("comment", "").strip()]
    except Exception:
        return []


def categorize(text):
    text = text.lower()
    if any(w in text for w in ["exam", "test", "quiz", "grade", "grading", "syllabus", "lecture", "class", "course", "professor", "teach"]):
        return "academics"
    if any(w in text for w in ["dorm", "housing", "room", "roommate", "residence"]):
        return "housing"
    if any(w in text for w in ["food", "dining", "cafeteria", "meal", "eat"]):
        return "dining"
    if any(w in text for w in ["party", "social", "friend", "club", "greek"]):
        return "social_life"
    if any(w in text for w in ["mental health", "counseling", "anxiety", "stress", "wellness"]):
        return "mental_health"
    if any(w in text for w in ["financial", "aid", "scholarship", "tuition", "cost", "money"]):
        return "financial_aid"
    return "academics"


def load_existing():
    if not os.path.exists(DATA_PATH):
        return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def collect_missing():
    os.makedirs("data", exist_ok=True)

    existing = load_existing()
    existing_tags = {r["school_tag"] for r in existing}
    print(f"Existing data: {len(existing)} reviews for schools: {existing_tags}")

    new_reviews = []

    for school_name, school_tag in MISSING_SCHOOLS.items():
        if school_tag in existing_tags:
            print(f"\nSkipping {school_name} — already have data")
            continue

        print(f"\n{'='*50}")
        print(f"Collecting: {school_name} ({school_tag})")
        print(f"{'='*50}")

        school_id = get_school_id(school_name)
        if not school_id:
            print(f"  ✗ Could not find school ID — skipping")
            continue

        time.sleep(1.5)  # pause between school lookups

        professors = get_professors(school_id)
        if not professors:
            print(f"  ✗ No professors found — skipping")
            continue

        # Take top 60 most-reviewed professors
        target_profs = professors[:60]
        school_reviews = []

        for i, prof in enumerate(target_profs):
            prof_name = f"{prof['firstName']} {prof['lastName']}"
            dept = prof.get("department", "Unknown")
            print(f"  [{i+1}/{len(target_profs)}] {prof_name} ({dept}) — {prof.get('numRatings',0)} ratings")

            ratings = get_ratings(prof["id"], max_ratings=20)

            for r in ratings:
                school_reviews.append({
                    "source": "rate_my_professors",
                    "school": school_name,
                    "school_tag": school_tag,
                    "professor_name": prof_name,
                    "department": dept,
                    "avg_rating": prof.get("avgRating"),
                    "avg_difficulty": prof.get("avgDifficulty"),
                    "would_take_again_pct": prof.get("wouldTakeAgainPercent"),
                    "course": r.get("class", ""),
                    "comment": r.get("comment", ""),
                    "helpful_rating": r.get("helpfulRating"),
                    "clarity_rating": r.get("clarityRating"),
                    "difficulty_rating": r.get("difficultyRating"),
                    "would_take_again": r.get("wouldTakeAgain"),
                    "grade": r.get("grade", ""),
                    "date": r.get("date", ""),
                    "category": categorize(r.get("comment", "")),
                })

            # Polite delay — vary it so it doesn't look like a bot
            time.sleep(random.uniform(0.8, 1.5))

        print(f"  ✓ Collected {len(school_reviews)} reviews for {school_name}")
        new_reviews.extend(school_reviews)

        # Save progress after each school — atomic write to prevent corruption
        all_reviews = existing + new_reviews
        tmp_path = DATA_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(all_reviews, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, DATA_PATH)  # atomic on same filesystem
        print(f"  💾 Saved progress — {len(all_reviews)} total reviews")

        time.sleep(3)  # longer pause between schools

    print(f"\n✅ Done! Added {len(new_reviews)} new reviews")
    print(f"✅ Total in {DATA_PATH}: {len(existing) + len(new_reviews)} reviews")


if __name__ == "__main__":
    collect_missing()
