"""
collect_reddit.py
Collects posts and comments from university subreddits using the Reddit API.
Saves to data/reddit_reviews.json in the same schema as RMP reviews.

Setup:
  1. Go to https://www.reddit.com/prefs/apps → create a "script" app
  2. Add to .env:
       REDDIT_CLIENT_ID=your_client_id
       REDDIT_CLIENT_SECRET=your_client_secret
       REDDIT_USER_AGENT=CampusVoice/1.0

  3. pip install praw
  4. python collect_reddit.py
"""

import os
import json
import time
from dotenv import load_dotenv

load_dotenv()

try:
    import praw
except ImportError:
    print("Install PRAW first:  pip install praw")
    exit(1)

OUTPUT_PATH = "data/reddit_reviews.json"

# Subreddit → (school full name, school_tag)
SUBREDDITS = {
    "UTK":             ("University of Tennessee Knoxville", "utk"),
    "vanderbilt":      ("Vanderbilt University", "vanderbilt"),
    "gatech":          ("Georgia Institute of Technology", "gatech"),
    "ufl":             ("University of Florida", "uf"),
    "uofm":            ("University of Michigan", "umich"),
    "ucla":            ("UCLA", "ucla"),
    "Duke":            ("Duke University", "duke"),
}

# Keywords that suggest academic/campus life content worth indexing
RELEVANT_KEYWORDS = [
    "professor", "class", "course", "major", "department", "lecture",
    "exam", "grade", "grading", "homework", "assignment", "syllabus",
    "TA", "teaching", "research", "internship", "campus", "dorm",
    "housing", "dining", "food", "tuition", "financial aid", "scholarship",
    "workload", "stress", "mental health", "social", "club", "greek",
    "parking", "registration", "advisor", "curriculum", "degree",
]

# Posts to fetch per subreddit (hot + top of year)
POSTS_PER_FEED = 100


def make_reddit():
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "CampusVoice/1.0 (by u/campusvoice_bot)")

    if not client_id or not client_secret:
        raise ValueError(
            "Missing REDDIT_CLIENT_ID or REDDIT_CLIENT_SECRET in .env\n"
            "Create a Reddit app at: https://www.reddit.com/prefs/apps"
        )
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
    )


def is_relevant(text):
    """Return True if the text mentions academic or campus topics."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in RELEVANT_KEYWORDS)


def categorize(text):
    text = text.lower()
    if any(w in text for w in ["professor", "class", "course", "exam", "grade", "grading",
                                "lecture", "syllabus", "teach", "ta", "homework", "assignment"]):
        return "academics"
    if any(w in text for w in ["dorm", "housing", "room", "roommate", "apartment"]):
        return "housing"
    if any(w in text for w in ["food", "dining", "cafeteria", "meal", "eat", "restaurant"]):
        return "dining"
    if any(w in text for w in ["party", "social", "friend", "club", "greek", "fraternity", "sorority"]):
        return "social_life"
    if any(w in text for w in ["mental health", "counseling", "therapy", "anxiety", "stress", "burnout"]):
        return "mental_health"
    if any(w in text for w in ["financial", "aid", "scholarship", "tuition", "fafsa", "cost", "debt"]):
        return "financial_aid"
    if any(w in text for w in ["safe", "crime", "police", "security"]):
        return "safety"
    if any(w in text for w in ["career", "job", "internship", "recruit", "interview", "coop"]):
        return "career"
    return "academics"


def collect_subreddit(reddit, sub_name, school_name, school_tag, reviews):
    sub = reddit.subreddit(sub_name)
    count_before = len(reviews)

    feeds = [
        ("hot", sub.hot(limit=POSTS_PER_FEED)),
        ("top_year", sub.top("year", limit=POSTS_PER_FEED)),
    ]

    seen_ids = set()

    for feed_name, feed in feeds:
        for post in feed:
            if post.id in seen_ids:
                continue
            seen_ids.add(post.id)

            title = post.title or ""
            selftext = post.selftext or ""
            full_text = f"{title}. {selftext}".strip()

            if len(full_text) < 40:
                continue
            if not is_relevant(full_text):
                continue

            # Index the post itself as a review
            reviews.append({
                "source": "reddit",
                "school": school_name,
                "school_tag": school_tag,
                "professor_name": "",
                "department": "",
                "avg_rating": None,
                "avg_difficulty": None,
                "would_take_again_pct": None,
                "course": "",
                "comment": full_text[:1000],   # cap length
                "helpful_rating": None,
                "clarity_rating": None,
                "difficulty_rating": None,
                "would_take_again": None,
                "grade": "",
                "date": str(post.created_utc),
                "category": categorize(full_text),
                "reddit_score": post.score,
                "reddit_url": f"https://reddit.com{post.permalink}",
            })

            # Also grab top-level comments
            post.comments.replace_more(limit=0)
            for comment in post.comments[:10]:
                body = (comment.body or "").strip()
                if len(body) < 40:
                    continue
                if not is_relevant(body):
                    continue
                reviews.append({
                    "source": "reddit",
                    "school": school_name,
                    "school_tag": school_tag,
                    "professor_name": "",
                    "department": "",
                    "avg_rating": None,
                    "avg_difficulty": None,
                    "would_take_again_pct": None,
                    "course": "",
                    "comment": body[:800],
                    "helpful_rating": None,
                    "clarity_rating": None,
                    "difficulty_rating": None,
                    "would_take_again": None,
                    "grade": "",
                    "date": str(comment.created_utc),
                    "category": categorize(body),
                    "reddit_score": comment.score,
                    "reddit_url": f"https://reddit.com{post.permalink}",
                })

        time.sleep(1)  # pause between hot/top feeds

    added = len(reviews) - count_before
    return added


def collect_all():
    os.makedirs("data", exist_ok=True)
    reddit = make_reddit()
    all_reviews = []

    for sub_name, (school_name, school_tag) in SUBREDDITS.items():
        print(f"\nr/{sub_name} → {school_name}")
        try:
            added = collect_subreddit(reddit, sub_name, school_name, school_tag, all_reviews)
            print(f"  ✓ {added} relevant posts/comments collected")
        except Exception as e:
            print(f"  ✗ Error: {e}")

        time.sleep(2)

    print(f"\n✅ Total Reddit reviews: {len(all_reviews)}")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_reviews, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved to {OUTPUT_PATH}")

    # Show breakdown
    from collections import Counter
    counts = Counter(r["school_tag"] for r in all_reviews)
    for tag, n in sorted(counts.items()):
        print(f"  {tag:15} {n:4} entries")


if __name__ == "__main__":
    collect_all()
