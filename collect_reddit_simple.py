"""
collect_reddit_simple.py
Collects posts/comments from university subreddits using Reddit's free public JSON API.
NO credentials, NO OAuth, NO PRAW — just plain HTTP requests.

Run:
    python collect_reddit_simple.py

Output: data/reddit_reviews.json  (auto-merged into reviews.json at the end)
"""

import requests
import json
import time
import os
import random
from collections import Counter

OUTPUT_PATH     = "data/reddit_reviews.json"
REVIEWS_PATH    = "data/reviews.json"

HEADERS = {
    "User-Agent": "CampusVoice/1.0 (research project; contact: campusvoice@example.com)"
}

# subreddit → (school full name, school_tag)
SUBREDDITS = {
    "UTK":        ("University of Tennessee Knoxville", "utk"),
    "vanderbilt": ("Vanderbilt University",             "vanderbilt"),
    "gatech":     ("Georgia Institute of Technology",   "gatech"),
    "ufl":        ("University of Florida",             "uf"),
    "uofm":       ("University of Michigan",            "umich"),
    "ucla":       ("UCLA",                              "ucla"),
    "Duke":       ("Duke University",                   "duke"),
}

# Keywords — only keep posts/comments that mention academic/campus topics
KEYWORDS = [
    "professor","class","course","major","department","lecture","exam","grade",
    "grading","homework","assignment","syllabus","ta","teaching","research",
    "internship","campus","dorm","housing","dining","food","tuition",
    "financial aid","scholarship","workload","stress","mental health","social",
    "club","greek","parking","registration","advisor","degree","gpa",
    "difficult","easy","recommend","avoid","best","worst","love","hate",
]

def is_relevant(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in KEYWORDS)

def categorize(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["professor","class","course","exam","grade","grading",
                             "lecture","syllabus","teach","ta","homework","assignment","gpa"]):
        return "academics"
    if any(w in t for w in ["dorm","housing","room","roommate","apartment"]):
        return "housing"
    if any(w in t for w in ["food","dining","cafeteria","meal","eat"]):
        return "dining"
    if any(w in t for w in ["party","social","friend","club","greek","fraternity","sorority"]):
        return "social_life"
    if any(w in t for w in ["mental health","counseling","anxiety","stress","burnout","wellness"]):
        return "mental_health"
    if any(w in t for w in ["financial","aid","scholarship","tuition","cost","money","fafsa"]):
        return "financial_aid"
    if any(w in t for w in ["career","job","internship","recruit","interview","coop"]):
        return "career"
    return "academics"

def fetch_json(url: str, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 429:
                wait = 60 + random.uniform(5, 15)
                print(f"    Rate limited — waiting {wait:.0f}s...")
                time.sleep(wait)
                continue
            if r.status_code != 200:
                print(f"    HTTP {r.status_code} for {url}")
                return None
            return r.json()
        except Exception as e:
            print(f"    Error: {e}")
            time.sleep(3 * (attempt + 1))
    return None

def collect_subreddit(sub_name: str, school_name: str, school_tag: str) -> list:
    reviews = []
    seen_ids = set()

    feeds = [
        f"https://www.reddit.com/r/{sub_name}/hot.json?limit=100",
        f"https://www.reddit.com/r/{sub_name}/top.json?t=year&limit=100",
        f"https://www.reddit.com/r/{sub_name}/top.json?t=all&limit=100",
    ]

    for feed_url in feeds:
        data = fetch_json(feed_url)
        if not data:
            continue

        posts = data.get("data", {}).get("children", [])
        print(f"    {feed_url.split('/')[-1].split('?')[0]:10} — {len(posts)} posts")

        for post_data in posts:
            post = post_data.get("data", {})
            post_id = post.get("id", "")
            if post_id in seen_ids:
                continue
            seen_ids.add(post_id)

            title    = post.get("title", "") or ""
            selftext = post.get("selftext", "") or ""
            full_text = f"{title}. {selftext}".strip()

            if len(full_text) < 40 or not is_relevant(full_text):
                continue

            reviews.append({
                "source":               "reddit",
                "school":               school_name,
                "school_tag":           school_tag,
                "professor_name":       "",
                "department":           "",
                "avg_rating":           None,
                "avg_difficulty":       None,
                "would_take_again_pct": None,
                "course":               "",
                "comment":              full_text[:1000],
                "helpful_rating":       None,
                "clarity_rating":       None,
                "difficulty_rating":    None,
                "would_take_again":     None,
                "grade":                "",
                "date":                 str(post.get("created_utc", "")),
                "category":             categorize(full_text),
                "reddit_score":         post.get("score", 0),
                "reddit_url":           f"https://reddit.com{post.get('permalink','')}",
            })

            # Fetch top comments for this post
            comments_url = f"https://www.reddit.com/r/{sub_name}/comments/{post_id}.json?limit=20&depth=1"
            cdata = fetch_json(comments_url)
            if cdata and len(cdata) > 1:
                comment_listing = cdata[1].get("data", {}).get("children", [])
                for c in comment_listing:
                    body = (c.get("data", {}).get("body") or "").strip()
                    if len(body) < 40 or not is_relevant(body):
                        continue
                    reviews.append({
                        "source":               "reddit",
                        "school":               school_name,
                        "school_tag":           school_tag,
                        "professor_name":       "",
                        "department":           "",
                        "avg_rating":           None,
                        "avg_difficulty":       None,
                        "would_take_again_pct": None,
                        "course":               "",
                        "comment":              body[:800],
                        "helpful_rating":       None,
                        "clarity_rating":       None,
                        "difficulty_rating":    None,
                        "would_take_again":     None,
                        "grade":                "",
                        "date":                 str(c.get("data", {}).get("created_utc", "")),
                        "category":             categorize(body),
                        "reddit_score":         c.get("data", {}).get("score", 0),
                        "reddit_url":           f"https://reddit.com{post.get('permalink','')}",
                    })

            time.sleep(random.uniform(1.5, 2.5))  # polite delay between posts

        time.sleep(random.uniform(2, 4))  # pause between feeds

    return reviews


def collect_all():
    os.makedirs("data", exist_ok=True)
    all_reddit = []

    for sub_name, (school_name, school_tag) in SUBREDDITS.items():
        print(f"\nr/{sub_name} → {school_name}")
        try:
            reviews = collect_subreddit(sub_name, school_name, school_tag)
            print(f"  ✓ {len(reviews)} relevant entries collected")
            all_reddit.extend(reviews)
        except Exception as e:
            print(f"  ✗ Failed: {e}")
        time.sleep(random.uniform(3, 5))

    # Save reddit file
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_reddit, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Saved {len(all_reddit)} Reddit entries to {OUTPUT_PATH}")

    # Merge into main reviews.json
    existing = []
    if os.path.exists(REVIEWS_PATH):
        with open(REVIEWS_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)

    existing_comments = {r["comment"] for r in existing}
    new_entries = [r for r in all_reddit if r["comment"] not in existing_comments]
    combined = existing + new_entries

    with open(REVIEWS_PATH, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    print(f"✅ Merged into {REVIEWS_PATH} — {len(combined)} total reviews")
    print("\nBreakdown by school:")
    counts = Counter(r["school_tag"] for r in combined)
    for tag, n in sorted(counts.items()):
        print(f"  {tag:15} {n:5} reviews")

    print("\nNext: run  python ingest.py  to push to Elasticsearch")


if __name__ == "__main__":
    collect_all()
