"""
collect_rmp.py
Fetches professor reviews from Rate My Professors for multiple universities.
Saves results to data/reviews.json
"""

import requests
import json
import time
import os

RMP_URL = "https://www.ratemyprofessors.com/graphql"
HEADERS = {
    "Authorization": "Basic dGVzdDp0ZXN0",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.ratemyprofessors.com/",
}

SCHOOLS = {
    "University of Tennessee Knoxville": "utk",
    "Vanderbilt University": "vanderbilt",
    "Georgia Institute of Technology": "gatech",
    "University of Florida": "uf",
    "University of Michigan": "umich",
    "UCLA": "ucla",
    "Duke University": "duke",
}


def get_school_id(school_name):
    query = """
    query NewSearchSchoolsQuery($query: SchoolSearchQuery!) {
      newSearch {
        schools(query: $query) {
          edges {
            node {
              id
              name
              city
              state
            }
          }
        }
      }
    }
    """
    resp = requests.post(
        RMP_URL,
        headers=HEADERS,
        json={"query": query, "variables": {"query": {"text": school_name}}},
    )
    edges = resp.json()["data"]["newSearch"]["schools"]["edges"]
    if not edges:
        print(f"  School not found: {school_name}")
        return None
    node = edges[0]["node"]
    print(f"  Found: {node['name']} ({node['city']}, {node['state']}) → ID: {node['id']}")
    return node["id"]


def get_professors(school_id, max_count=200):
    query = """
    query TeacherSearchResultsPageQuery($query: TeacherSearchQuery!) {
      search: newSearch {
        teachers(query: $query, first: 200) {
          edges {
            node {
              id
              firstName
              lastName
              department
              avgRating
              avgDifficulty
              numRatings
              wouldTakeAgainPercent
            }
          }
        }
      }
    }
    """
    resp = requests.post(
        RMP_URL,
        headers=HEADERS,
        json={
            "query": query,
            "variables": {"query": {"text": "", "schoolID": school_id}},
        },
    )
    data = resp.json()
    edges = data["data"]["search"]["teachers"]["edges"]
    professors = [e["node"] for e in edges]
    print(f"  Found {len(professors)} professors")
    return professors


def get_ratings(professor_id, max_ratings=20):
    query = """
    query RatingsListQuery($id: ID!, $count: Int) {
      node(id: $id) {
        ... on Teacher {
          ratings(first: $count) {
            edges {
              node {
                comment
                class
                date
                helpfulRating
                clarityRating
                difficultyRating
                wouldTakeAgain
                grade
              }
            }
          }
        }
      }
    }
    """
    resp = requests.post(
        RMP_URL,
        headers=HEADERS,
        json={
            "query": query,
            "variables": {"id": professor_id, "count": max_ratings},
        },
    )
    data = resp.json()
    try:
        edges = data["data"]["node"]["ratings"]["edges"]
        return [e["node"] for e in edges if e["node"]["comment"]]
    except Exception:
        return []


def collect_all(output_path="data/reviews.json"):
    os.makedirs("data", exist_ok=True)
    all_reviews = []

    for school_name, school_tag in SCHOOLS.items():
        print(f"\n--- {school_name} ---")
        school_id = get_school_id(school_name)
        if not school_id:
            continue

        professors = get_professors(school_id)

        for i, prof in enumerate(professors[:50]):  # limit to 50 profs for demo
            prof_name = f"{prof['firstName']} {prof['lastName']}"
            print(f"  [{i+1}/{min(50, len(professors))}] {prof_name} ({prof['department']})")

            ratings = get_ratings(prof["id"], max_ratings=15)
            time.sleep(0.3)  # be polite to the server

            for r in ratings:
                all_reviews.append({
                    "source": "rate_my_professors",
                    "school": school_name,
                    "school_tag": school_tag,
                    "professor_name": prof_name,
                    "department": prof.get("department", "Unknown"),
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

    print(f"\n✅ Collected {len(all_reviews)} reviews total")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_reviews, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved to {output_path}")
    return all_reviews


def categorize(text):
    """Simple keyword-based category tagger."""
    text = text.lower()
    if any(w in text for w in ["exam", "test", "quiz", "grade", "grading", "syllabus", "lecture", "class", "course", "professor", "teach"]):
        return "academics"
    if any(w in text for w in ["dorm", "housing", "room", "roommate", "residence"]):
        return "housing"
    if any(w in text for w in ["food", "dining", "cafeteria", "meal", "eat"]):
        return "dining"
    if any(w in text for w in ["party", "social", "friend", "club", "greek", "life"]):
        return "social_life"
    if any(w in text for w in ["mental health", "counseling", "therapy", "anxiety", "stress", "wellness"]):
        return "mental_health"
    if any(w in text for w in ["financial", "aid", "scholarship", "tuition", "fafsa", "cost", "money"]):
        return "financial_aid"
    if any(w in text for w in ["safe", "crime", "security", "police", "campus"]):
        return "safety"
    return "academics"  # default for RMP


if __name__ == "__main__":
    collect_all()
