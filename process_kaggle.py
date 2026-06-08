"""
process_kaggle.py
Converts a downloaded Kaggle Rate My Professors CSV into campus_reviews format.
Filters to only the 7 universities used by CampusVoice.
Merges with existing data/reviews.json (keeps UTK + Vanderbilt already collected).

Usage:
    python process_kaggle.py --csv path/to/downloaded.csv

Tested against these Kaggle datasets (both work):
  - https://www.kaggle.com/datasets/thedevastator/rate-my-professor-us-college-faculty-ratings
  - https://www.kaggle.com/datasets/timschaum/ratemyprofessor
"""

import json
import os
import argparse
import csv
from collections import Counter

OUTPUT_PATH = "data/reviews.json"

# Map of name fragments (lowercase) → school_tag
# We do substring matching so partial names still match
SCHOOL_MAP = {
    "tennessee":                        ("University of Tennessee Knoxville", "utk"),
    "vanderbilt":                       ("Vanderbilt University",             "vanderbilt"),
    "georgia institute of technology":  ("Georgia Institute of Technology",   "gatech"),
    "georgia tech":                     ("Georgia Institute of Technology",   "gatech"),
    "gatech":                           ("Georgia Institute of Technology",   "gatech"),
    "university of florida":            ("University of Florida",             "uf"),
    "university of michigan":           ("University of Michigan",            "umich"),
    "michigan ann arbor":               ("University of Michigan",            "umich"),
    "university of california los angeles": ("UCLA",                          "ucla"),
    "ucla":                             ("UCLA",                              "ucla"),
    "duke":                             ("Duke University",                   "duke"),
}

def match_school(name: str):
    """Return (school_full, school_tag) or None if not one of our 7 schools."""
    name_lower = name.lower().strip()
    for fragment, result in SCHOOL_MAP.items():
        if fragment in name_lower:
            return result
    return None


def categorize(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["exam","test","quiz","grade","grading","syllabus","lecture",
                             "class","course","professor","teach","hw","homework","assignment"]):
        return "academics"
    if any(w in t for w in ["dorm","housing","room","roommate","residence","apartment"]):
        return "housing"
    if any(w in t for w in ["food","dining","cafeteria","meal","eat"]):
        return "dining"
    if any(w in t for w in ["party","social","friend","club","greek","fraternity","sorority"]):
        return "social_life"
    if any(w in t for w in ["mental health","counseling","anxiety","stress","wellness","burnout"]):
        return "mental_health"
    if any(w in t for w in ["financial","aid","scholarship","tuition","cost","money","fafsa"]):
        return "financial_aid"
    if any(w in t for w in ["safe","crime","police","security"]):
        return "safety"
    if any(w in t for w in ["career","job","internship","recruit","interview"]):
        return "career"
    return "academics"


def safe_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def detect_columns(header: list) -> dict:
    """
    Auto-detect column names from the CSV header (case-insensitive).
    Returns a dict mapping our field names → actual CSV column name.
    Handles the two most common Kaggle RMP CSV formats.
    """
    h = {col.lower().strip(): col for col in header}

    def find(*candidates):
        for c in candidates:
            if c in h:
                return h[c]
        return None

    return {
        "school":       find("school_name", "school", "institution", "university"),
        "professor":    find("professor_name", "professor", "teacher_name", "name", "faculty_name"),
        "department":   find("department", "dept", "subject"),
        "course":       find("course", "class", "course_name", "class_name"),
        "comment":      find("comments", "comment", "review", "text", "review_text"),
        "rating":       find("student_star", "rating", "avg_rating", "quality", "overall_quality"),
        "difficulty":   find("student_difficult", "difficulty", "avg_difficulty", "difficulty_level"),
        "helpful":      find("helpful_rating", "helpfulness", "helpful"),
        "clarity":      find("clarity_rating", "clarity"),
        "date":         find("date", "created_at", "review_date"),
    }


def process_csv(csv_path: str) -> list:
    reviews = []
    skipped_school = 0
    skipped_no_comment = 0

    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        cols = detect_columns(reader.fieldnames or [])

        print(f"Detected columns: {cols}")

        if not cols["school"]:
            raise ValueError("Could not find a school/university column in the CSV. "
                             "Check that you downloaded the right dataset.")
        if not cols["comment"]:
            raise ValueError("Could not find a comment/review column in the CSV.")

        for i, row in enumerate(reader):
            school_raw = row.get(cols["school"], "").strip()
            matched = match_school(school_raw)
            if not matched:
                skipped_school += 1
                continue

            school_name, school_tag = matched
            comment = row.get(cols["comment"], "").strip() if cols["comment"] else ""
            if not comment or len(comment) < 20:
                skipped_no_comment += 1
                continue

            professor = row.get(cols["professor"], "").strip() if cols["professor"] else ""
            department = row.get(cols["department"], "").strip() if cols["department"] else ""
            course = row.get(cols["course"], "").strip() if cols["course"] else ""
            rating = safe_float(row.get(cols["rating"]) if cols["rating"] else None)
            difficulty = safe_float(row.get(cols["difficulty"]) if cols["difficulty"] else None)
            helpful = safe_float(row.get(cols["helpful"]) if cols["helpful"] else None)
            clarity = safe_float(row.get(cols["clarity"]) if cols["clarity"] else None)
            date = row.get(cols["date"], "") if cols["date"] else ""

            reviews.append({
                "source": "kaggle_rmp",
                "school": school_name,
                "school_tag": school_tag,
                "professor_name": professor,
                "department": department,
                "avg_rating": rating,
                "avg_difficulty": difficulty,
                "would_take_again_pct": None,
                "course": course,
                "comment": comment[:1200],
                "helpful_rating": helpful,
                "clarity_rating": clarity,
                "difficulty_rating": difficulty,
                "would_take_again": None,
                "grade": "",
                "date": date,
                "category": categorize(comment),
            })

            if (i + 1) % 10000 == 0:
                print(f"  Processed {i+1} rows, kept {len(reviews)} so far...")

    print(f"\n  Skipped {skipped_school} rows (not one of our 7 schools)")
    print(f"  Skipped {skipped_no_comment} rows (no comment text)")
    return reviews


def merge_and_save(new_reviews: list):
    existing = []
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
        print(f"\nExisting reviews: {len(existing)}")
    else:
        print("\nNo existing reviews.json — starting fresh")

    # Avoid duplicating exact same comments
    existing_comments = {r["comment"] for r in existing}
    deduped = [r for r in new_reviews if r["comment"] not in existing_comments]
    print(f"New reviews (after dedup): {len(deduped)}")

    combined = existing + deduped
    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved {len(combined)} total reviews to {OUTPUT_PATH}")

    counts = Counter(r["school_tag"] for r in combined)
    print("\nBreakdown by school:")
    for tag, n in sorted(counts.items()):
        print(f"  {tag:15} {n:5} reviews")


def main():
    parser = argparse.ArgumentParser(description="Process Kaggle RMP CSV into CampusVoice format")
    parser.add_argument("--csv", required=True, help="Path to the downloaded Kaggle CSV file")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"File not found: {args.csv}")
        return

    print(f"Processing: {args.csv}")
    new_reviews = process_csv(args.csv)
    print(f"\nMatched {len(new_reviews)} reviews for our 7 universities")

    merge_and_save(new_reviews)
    print("\nNext step: run  python ingest.py  to index into Elasticsearch")


if __name__ == "__main__":
    main()
