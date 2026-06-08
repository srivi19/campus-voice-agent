"""
collect_niche.py
Scrapes student reviews from Niche.com for all 7 universities.
No API key needed — Niche serves fully server-rendered HTML.

Run:
    pip install beautifulsoup4
    python collect_niche.py

Output: data/niche_reviews.json  (auto-merged into reviews.json at the end)
"""

import requests
import json
import os
import time
import random
import re
from bs4 import BeautifulSoup
from collections import Counter

OUTPUT_PATH  = "data/niche_reviews.json"
REVIEWS_PATH = "data/reviews.json"
PAGES_PER_SCHOOL = 15   # ~20 reviews/page → ~300 reviews per school

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.google.com/",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-User": "?1",
    "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
}

# Niche URL slug → (school full name, school_tag)
SCHOOLS = {
    "university-of-tennessee-knoxville":   ("University of Tennessee Knoxville", "utk"),
    "vanderbilt-university":               ("Vanderbilt University",             "vanderbilt"),
    "georgia-institute-of-technology":     ("Georgia Institute of Technology",   "gatech"),
    "university-of-florida":               ("University of Florida",             "uf"),
    "university-of-michigan-ann-arbor":    ("University of Michigan",            "umich"),
    "university-of-california-los-angeles":("UCLA",                              "ucla"),
    "duke-university":                     ("Duke University",                   "duke"),
}

STUDENT_TYPES = {
    "freshman", "sophomore", "junior", "senior",
    "graduate student", "alum", "alumni", "other",
}


def categorize(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["professor","class","course","exam","grade","grading",
                             "lecture","syllabus","teach","ta","homework","assignment","gpa","major"]):
        return "academics"
    if any(w in t for w in ["dorm","housing","room","roommate","apartment","residence hall"]):
        return "housing"
    if any(w in t for w in ["food","dining","cafeteria","meal","eat","restaurant","dining hall"]):
        return "dining"
    if any(w in t for w in ["party","social","friend","club","greek","fraternity","sorority","sports"]):
        return "social_life"
    if any(w in t for w in ["mental health","counseling","therapy","anxiety","stress","burnout","wellness"]):
        return "mental_health"
    if any(w in t for w in ["financial","aid","scholarship","tuition","cost","money","fafsa","afford"]):
        return "financial_aid"
    if any(w in t for w in ["safe","crime","police","security"]):
        return "safety"
    if any(w in t for w in ["career","job","internship","recruit","interview","networking"]):
        return "career"
    return "academics"


def safe_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def parse_reviews(soup) -> list:
    """
    Extract reviews from a Niche college reviews page.
    Tries multiple selector strategies for resilience.
    """
    reviews = []

    # Strategy 1: find all elements with itemprop="reviewBody" (schema.org markup)
    bodies = soup.select('[itemprop="reviewBody"]')
    if bodies:
        for body_el in bodies:
            text = body_el.get_text(strip=True)
            if len(text) < 30:
                continue

            # Walk up to find the parent review container
            container = body_el
            for _ in range(5):
                container = container.parent
                if container is None:
                    break
                # Look for rating
                rating_el = container.select_one('[itemprop="ratingValue"]')
                if rating_el:
                    break

            rating = None
            if rating_el:
                rating = safe_float(rating_el.get("content") or rating_el.get_text())

            # Student type + date from nearby text
            student_type = ""
            date_str = ""
            if container:
                meta_text = container.get_text(" | ", strip=True).lower()
                for stype in STUDENT_TYPES:
                    if stype in meta_text:
                        student_type = stype.title()
                        break
                # Date: look for "X days/months/years ago"
                date_match = re.search(r"(\d+\s+(?:day|month|year|week)s?\s+ago|yesterday|just now)", meta_text)
                if date_match:
                    date_str = date_match.group(0)

            reviews.append({
                "text": text[:1200],
                "rating": rating,
                "student_type": student_type,
                "date": date_str,
            })
        return reviews

    # Strategy 2: look for review cards by common Niche class patterns
    selectors = [
        "section.review",
        "[class*='ReviewCard']",
        "[class*='review-card']",
        "[class*='Card__body']",
        "article",
    ]
    cards = []
    for sel in selectors:
        cards = soup.select(sel)
        if cards:
            break

    for card in cards:
        text_el = card.find("p") or card.find("blockquote")
        if not text_el:
            continue
        text = text_el.get_text(strip=True)
        if len(text) < 30:
            continue

        # Rating
        rating = None
        rating_el = card.find(attrs={"title": re.compile(r"\d out of 5")})
        if not rating_el:
            rating_el = card.find(string=re.compile(r"Rating \d out of 5"))
        if rating_el:
            m = re.search(r"(\d)", str(rating_el))
            if m:
                rating = float(m.group(1))

        # Student type
        student_type = ""
        card_text = card.get_text(" ", strip=True).lower()
        for stype in STUDENT_TYPES:
            if stype in card_text:
                student_type = stype.title()
                break

        # Date
        date_str = ""
        date_match = re.search(r"(\d+\s+(?:day|month|year|week)s?\s+ago|yesterday)", card_text)
        if date_match:
            date_str = date_match.group(0)

        reviews.append({
            "text": text[:1200],
            "rating": rating,
            "student_type": student_type,
            "date": date_str,
        })

    # Strategy 3: regex fallback on raw text if nothing found
    if not reviews:
        full_text = soup.get_text("\n", strip=True)
        # Match review blocks: "Rating X out of 5" followed by text
        blocks = re.split(r"Rating \d out of 5", full_text)
        for block in blocks[1:]:  # skip first (header)
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            # Skip very short blocks and boilerplate
            if len(lines) < 3:
                continue
            # Skip metadata lines at start (reviews, number)
            text_lines = [l for l in lines[:10] if not re.match(r"^\d+$|^reviews$|^Report$", l, re.I)]
            text = " ".join(text_lines[:6])
            if len(text) < 40:
                continue
            # Student type
            student_type = ""
            block_lower = block.lower()
            for stype in STUDENT_TYPES:
                if f"- {stype}" in block_lower:
                    student_type = stype.title()
                    break
            reviews.append({
                "text": text[:1200],
                "rating": None,
                "student_type": student_type,
                "date": "",
            })

    return reviews


def make_session() -> requests.Session:
    """Create a session that looks like a real browser — hits homepage first to get cookies."""
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        # Warm-up: visit homepage to collect cookies like a real browser
        session.get("https://www.niche.com/", timeout=15)
        time.sleep(random.uniform(2, 4))
        # Then visit the colleges section
        session.get("https://www.niche.com/colleges/", timeout=15)
        time.sleep(random.uniform(1, 3))
    except Exception:
        pass
    return session


_session = None

def collect_school(slug: str, school_name: str, school_tag: str) -> list:
    global _session
    if _session is None:
        print("  Warming up session...")
        _session = make_session()

    all_reviews = []
    base_url = f"https://www.niche.com/colleges/{slug}/reviews/"

    for page in range(1, PAGES_PER_SCHOOL + 1):
        url = base_url if page == 1 else f"{base_url}?page={page}"

        for attempt in range(3):
            try:
                r = _session.get(url, timeout=20)
                if r.status_code == 404:
                    print(f"    404 — stopping at page {page}")
                    return all_reviews
                if r.status_code == 429:
                    wait = 60 + random.uniform(10, 20)
                    print(f"    Rate limited — waiting {wait:.0f}s...")
                    time.sleep(wait)
                    continue
                r.raise_for_status()
                break
            except Exception as e:
                print(f"    Attempt {attempt+1} failed: {e}")
                time.sleep(5 * (attempt + 1))
        else:
            print(f"    Skipping page {page} after 3 failures")
            continue

        soup = BeautifulSoup(r.text, "html.parser")
        page_reviews = parse_reviews(soup)

        if not page_reviews:
            print(f"    Page {page}: no reviews found — stopping")
            break

        print(f"    Page {page}: {len(page_reviews)} reviews")

        for rev in page_reviews:
            all_reviews.append({
                "source": "niche",
                "school": school_name,
                "school_tag": school_tag,
                "professor_name": "",
                "department": "",
                "avg_rating": rev["rating"],
                "avg_difficulty": None,
                "would_take_again_pct": None,
                "course": "",
                "comment": rev["text"],
                "helpful_rating": rev["rating"],
                "clarity_rating": None,
                "difficulty_rating": None,
                "would_take_again": None,
                "grade": "",
                "date": rev["date"],
                "category": categorize(rev["text"]),
                "student_type": rev["student_type"],
                "niche_url": base_url,
            })

        time.sleep(random.uniform(2, 4))

    return all_reviews


def collect_all():
    os.makedirs("data", exist_ok=True)
    all_niche = []

    for slug, (school_name, school_tag) in SCHOOLS.items():
        print(f"\n{school_name} ({school_tag})")
        print(f"  URL: https://www.niche.com/colleges/{slug}/reviews/")
        try:
            reviews = collect_school(slug, school_name, school_tag)
            print(f"  ✓ {len(reviews)} reviews collected")
            all_niche.extend(reviews)
        except Exception as e:
            print(f"  ✗ Failed: {e}")
        time.sleep(random.uniform(4, 7))

    # Save niche file
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_niche, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Saved {len(all_niche)} Niche reviews to {OUTPUT_PATH}")

    # Merge into main reviews.json
    existing = []
    if os.path.exists(REVIEWS_PATH):
        with open(REVIEWS_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)

    existing_comments = {r["comment"][:100] for r in existing}
    new_entries = [r for r in all_niche if r["comment"][:100] not in existing_comments]
    combined = existing + new_entries

    with open(REVIEWS_PATH, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    print(f"✅ Merged into {REVIEWS_PATH} — {len(combined)} total reviews")
    print("\nBreakdown by school:")
    counts = Counter(r["school_tag"] for r in combined)
    for tag, n in sorted(counts.items()):
        print(f"  {tag:15} {n:5} reviews")

    print("\nBreakdown by source:")
    sources = Counter(r["source"] for r in combined)
    for src, n in sorted(sources.items()):
        print(f"  {src:25} {n:5} reviews")

    print("\nNext: run  python ingest.py  to push to Elasticsearch")


if __name__ == "__main__":
    collect_all()
