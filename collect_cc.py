"""
collect_cc.py
Scrapes academic posts from College Confidential (talk.collegeconfidential.com)
using its public Discourse JSON API. No authentication needed.
Filters to 2024-01-01 onwards only.

Usage:
    python collect_cc.py

Output: data/cc_posts.json  (same schema as reviews.json)
"""

import json
import os
import re
import time
import datetime
import requests
from html.parser import HTMLParser

# ── Config ─────────────────────────────────────────────────────────────────────
BASE       = "https://talk.collegeconfidential.com"
MIN_DATE   = datetime.date(2024, 1, 1)
MAX_SEARCH_PAGES = 5      # 50 results per page = up to 250 per query
SLEEP      = 1.5
DATA_PATH  = "data/cc_posts.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CampusVoice/1.0; educational project)",
    "Accept":     "application/json",
}

# ── University → search terms ──────────────────────────────────────────────────
UNIVERSITIES = [
    {
        "school":     "University of Tennessee Knoxville",
        "school_tag": "utk",
        "queries": [
            "UTK professor", "University Tennessee professor grade",
            "UTK class difficulty", "Tennessee Knoxville course",
        ],
    },
    {
        "school":     "Vanderbilt University",
        "school_tag": "vanderbilt",
        "queries": [
            "Vanderbilt professor", "Vanderbilt class grade",
            "Vanderbilt course difficulty", "Vanderbilt workload",
        ],
    },
    {
        "school":     "Georgia Institute of Technology",
        "school_tag": "gatech",
        "queries": [
            "Georgia Tech professor", "Gatech class grade",
            "Georgia Tech course difficulty", "Gatech workload",
        ],
    },
    {
        "school":     "University of Florida",
        "school_tag": "uf",
        "queries": [
            "UF professor", "University Florida professor grade",
            "UF class difficulty", "Gainesville course",
        ],
    },
    {
        "school":     "University of Michigan",
        "school_tag": "umich",
        "queries": [
            "Michigan professor", "UMich class grade",
            "University Michigan course difficulty", "UMich workload",
        ],
    },
    {
        "school":     "UCLA",
        "school_tag": "ucla",
        "queries": [
            "UCLA professor", "UCLA class grade",
            "UCLA course difficulty", "UCLA workload",
        ],
    },
    {
        "school":     "Duke University",
        "school_tag": "duke",
        "queries": [
            "Duke professor", "Duke class grade",
            "Duke course difficulty", "Duke workload",
        ],
    },
]

ACADEMIC_KEYWORDS = [
    "professor", "prof ", "instructor", "lecturer", "ta ",
    "class", "course", "exam", "midterm", "final", "quiz",
    "grade", "grading", "gpa", "curve", "syllabus",
    "homework", "assignment", "workload", "lecture",
    "major", "department", "semester", "credit",
    "difficult", "easy", "hard", "office hours",
]


# ── HTML stripper ──────────────────────────────────────────────────────────────
class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []

    def handle_data(self, data):
        self._parts.append(data)

    def get_text(self):
        return " ".join(self._parts)


def strip_html(html: str) -> str:
    s = HTMLStripper()
    s.feed(html)
    return re.sub(r"\s+", " ", s.get_text()).strip()


# ── Date helpers ───────────────────────────────────────────────────────────────
def parse_iso(date_str: str) -> datetime.date | None:
    if not date_str:
        return None
    try:
        # "2024-03-15T10:30:00.000Z"
        return datetime.date.fromisoformat(date_str[:10])
    except Exception:
        return None


def is_recent(date_str: str) -> bool:
    d = parse_iso(date_str)
    return d is None or d >= MIN_DATE


def is_academic(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in ACADEMIC_KEYWORDS)


# ── API calls ──────────────────────────────────────────────────────────────────
def search(session: requests.Session, query: str, page: int) -> dict:
    try:
        r = session.get(
            f"{BASE}/search.json",
            params={"q": query, "page": page},
            timeout=15,
        )
        if r.status_code == 429:
            print("    Rate limited — sleeping 30s")
            time.sleep(30)
            return {}
        if r.status_code != 200:
            print(f"    Search returned {r.status_code}")
            return {}
        return r.json()
    except Exception as e:
        print(f"    Search error: {e}")
        return {}


def get_topic_posts(session: requests.Session, topic_id: int) -> list[dict]:
    """Fetch all posts from a topic."""
    try:
        r = session.get(f"{BASE}/t/{topic_id}.json", timeout=15)
        if r.status_code != 200:
            return []
        data  = r.json()
        posts = data.get("post_stream", {}).get("posts", [])
        return posts
    except Exception:
        return []


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    os.makedirs("data", exist_ok=True)

    all_posts: list[dict] = []
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            all_posts = json.load(f)
        print(f"Loaded {len(all_posts)} existing CC posts")

    seen_post_ids: set[str] = {p.get("post_id") for p in all_posts if p.get("post_id")}
    new_count = 0

    session = requests.Session()
    session.headers.update(HEADERS)

    for uni in UNIVERSITIES:
        school     = uni["school"]
        school_tag = uni["school_tag"]
        print(f"\n{'─'*60}")
        print(f"  {school} ({school_tag})")

        seen_topics: set[int] = set()

        for query in uni["queries"]:
            print(f"  Query: \"{query}\"")

            for page in range(1, MAX_SEARCH_PAGES + 1):
                result = search(session, query, page)
                if not result:
                    break

                topics = result.get("topics", [])
                posts  = result.get("posts",  [])

                if not topics and not posts:
                    break

                # Collect topic IDs to fetch full posts
                topic_ids = {t["id"] for t in topics if "id" in t}
                for p in posts:
                    if "topic_id" in p:
                        topic_ids.add(p["topic_id"])

                new_topics = topic_ids - seen_topics
                seen_topics |= topic_ids

                added_this_page = 0
                for tid in new_topics:
                    topic_posts = get_topic_posts(session, tid)
                    time.sleep(0.5)

                    for post in topic_posts:
                        pid      = str(post.get("id", ""))
                        cooked   = post.get("cooked", "") or ""
                        text     = strip_html(cooked)
                        created  = post.get("created_at", "")

                        if not text or len(text) < 80:
                            continue
                        if not is_academic(text):
                            continue
                        if not is_recent(created):
                            continue
                        if pid in seen_post_ids:
                            continue

                        if len(text) > 2000:
                            text = text[:2000] + "…"

                        all_posts.append({
                            "school":            school,
                            "school_tag":        school_tag,
                            "source":            "college_confidential",
                            "topic_id":          tid,
                            "post_id":           pid,
                            "comment":           text,
                            "date":              created[:10] if created else "",
                            "url":               f"{BASE}/t/{tid}/{post.get('post_number',1)}",
                            # RMP-compatible nulls
                            "professor_name":    None,
                            "department":        None,
                            "course":            None,
                            "avg_rating":        None,
                            "helpful_rating":    None,
                            "clarity_rating":    None,
                            "difficulty_rating": None,
                            "category":          "college_confidential",
                        })
                        seen_post_ids.add(pid)
                        new_count += 1
                        added_this_page += 1

                print(f"    page {page}: {len(new_topics)} new topics → {added_this_page} posts added")

                if len(topics) < 10 and len(posts) < 10:
                    break   # no more results

                time.sleep(SLEEP)

    # Atomic write
    tmp = DATA_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(all_posts, f, indent=2, ensure_ascii=False)
    os.replace(tmp, DATA_PATH)

    print(f"\n✅ Done! Added {new_count} new posts (2024+). Total: {len(all_posts)}")
    print(f"   Saved to {DATA_PATH}")
    print(f"\nNext: python ingest.py")


if __name__ == "__main__":
    main()
