# CampusVoice — Architecture

🌐 **Live:** [campus-voice-agent-420887396772.us-east1.run.app](https://campus-voice-agent-420887396772.us-east1.run.app/)
💻 **GitHub:** [github.com/srivi19/campus-voice-agent](https://github.com/srivi19/campus-voice-agent)

---

## Overview

CampusVoice is an agentic AI app that answers natural-language questions about university professors and campus life using real student review data from two sources. It combines a Gemini LLM with an Elasticsearch backend via the Model Context Protocol (MCP).

```
User → Flask API → Gemini Agent → Elastic MCP Server → Elasticsearch
                        ↑                                     |
                        └─────────── tool results ────────────┘
```

---

## Data Sources

CampusVoice combines two complementary data sources into a single Elasticsearch index:

| Source | What it covers | Volume |
|--------|---------------|--------|
| **Rate My Professors** (GraphQL API) | Professor quality, grading, course difficulty, teaching style | ~6,000 reviews |
| **Reddit** (public JSON API — no credentials) | Campus life, housing, dining, workload, social life, student discussions | ~1,000+ posts & comments |

Together these give the agent both structured professor feedback and open-ended student discussions, making it possible to answer questions like *"What's campus life like at Michigan?"* (Reddit) alongside *"Which professors at UCLA are rated highest?"* (RMP).

### Reddit Collection — No API Key Required
Reddit's public `.json` endpoint (`reddit.com/r/<subreddit>.json`) returns post and comment data without any authentication. The collector hits hot posts, top posts of the year, and top-level comments from 7 university subreddits: r/UTK, r/vanderbilt, r/gatech, r/ufl, r/uofm, r/ucla, r/Duke.

---

## Component Breakdown

### 1. Web UI (`templates/index.html`)
A single-page app served by Flask. Users select a university tab, type a question, and receive an answer. Built with vanilla HTML/CSS/JS.

- University tabs: UTK, Vanderbilt, Georgia Tech, UF, Michigan, UCLA, Duke
- Suggested questions per university (covering both professor and campus life topics)
- Data source badges: Gemini 2.5, Elastic MCP Search, Rate My Professors, Reddit, Google Cloud Run

### 2. Flask API Server (`server.py`)
Thin HTTP layer with three endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serves the web UI |
| `/api/ask` | POST | Accepts `{question, school}`, returns `{answer}` |
| `/health` | GET | Cloud Run health check |

Validates input, optionally prefixes the question with a school filter, calls the agent, and returns the result as JSON.

### 3. Gemini Agent (`agent_mcp.py`)
The core reasoning layer. Runs a multi-turn function-calling loop:

1. Sends the user question + system prompt to Gemini 2.5 Flash
2. Gemini decides which Elasticsearch search to run (via function calling)
3. The MCP client executes the search and returns results
4. Gemini synthesizes the results into a final answer
5. Repeats up to 8 times until Gemini produces a text response

The system prompt instructs Gemini to:
- Try `school_tag` filter first, then fall back to `school` name match, then broad search — so it never gives up after one empty result
- Search Reddit content (`source: "reddit"`) for campus life questions
- Search RMP content (`source: "rate_my_professors"`) for professor/course questions
- Quote actual review and post text verbatim for credibility
- Compare schools by running two separate searches

Key design decisions:
- **3-tier search fallback** — school_tag → school name match → no filter, prevents empty responses
- **No aggregation queries** — the MCP server returns 0 results for agg-only queries
- **85-second time budget** — hard wall-clock limit before Cloud Run's 300s timeout
- **503 retry with backoff** — 5 attempts at 3s/6s/9s/12s intervals for Gemini API overload

### 4. MCP Client (inside `agent_mcp.py`)
A lightweight JSON-RPC over stdio client that:

1. Spawns `@elastic/mcp-server-elasticsearch` as a subprocess
2. Performs the MCP handshake (`initialize` → `notifications/initialized`)
3. Lists available tools (`tools/list`)
4. Calls tools on Gemini's behalf (`tools/call`)
5. Filters stdout for valid JSON-RPC lines (ignores Node.js telemetry noise)

### 5. Elastic MCP Server (subprocess)
`@elastic/mcp-server-elasticsearch` — an official Elastic npm package that:
- Connects to Elasticsearch Cloud using `ES_URL` + `ES_API_KEY`
- Exposes search, get, and index tools over MCP stdio
- Runs inside the same Docker container as the Python app

### 6. Elasticsearch (`campus_reviews` index)
Hosted on [Elastic Cloud Serverless](https://www.elastic.co/cloud). Stores 6,800+ reviews and discussions with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `source` | keyword | "rate_my_professors" or "reddit" |
| `school` | keyword | Full university name |
| `school_tag` | keyword | Short tag (utk, vanderbilt, gatech, uf, umich, ucla, duke) |
| `professor_name` | text | Professor full name (RMP only) |
| `department` | keyword | Academic department (RMP only) |
| `course` | keyword | Course code (RMP only) |
| `comment` | text | Full review or post text |
| `helpful_rating` | float | 1–5 helpfulness score (RMP only) |
| `clarity_rating` | float | 1–5 clarity score (RMP only) |
| `difficulty_rating` | float | 1–5 difficulty score (RMP only) |
| `avg_rating` | float | Professor's overall average rating (RMP only) |
| `category` | keyword | Auto-tagged: academics, housing, dining, social_life, mental_health, financial_aid, career, safety |
| `date` | date | Review or post date |
| `reddit_score` | integer | Reddit upvote score (Reddit only) |

### 7. Data Pipeline
Scripts run once to populate Elasticsearch:

| Script | Purpose |
|--------|---------|
| `collect_rmp.py` | GraphQL scraper for Rate My Professors |
| `collect_rmp_missing.py` | Targeted collector with retry logic for any schools with missing data |
| `collect_reddit_simple.py` | Reddit public JSON API collector — no credentials needed |
| `process_kaggle.py` | Optional: converts Kaggle RMP CSV exports to the same schema |
| `setup_index.py` | Creates the `campus_reviews` index with field mappings |
| `ingest.py` | Bulk-indexes all sources (`reviews.json` + `reddit_reviews.json`) |

---

## Deployment

### Container (`Dockerfile`)
```
python:3.11-slim
  └── Node.js 20 (via nodesource)
       └── @elastic/mcp-server-elasticsearch (npm global)
  └── Python dependencies (requirements.txt)
  └── Flask app (server.py)
```

Node.js and the MCP server are bundled into the same container — the Python agent spawns them as a subprocess per request.

### Google Cloud Run
- **Region:** us-east1
- **Scaling:** Min 0, Max 20 instances (auto-scales to zero when idle)
- **CPU:** 1 vCPU, 512 MiB RAM
- **Request timeout:** 300 seconds
- **Port:** 8080
- **CI/CD:** Auto-deploys from GitHub `main` branch via Cloud Build on every `git push`

### Environment Variables (set in Cloud Run)
```
GEMINI_API_KEY         — Google AI Studio key
ELASTICSEARCH_URL      — Elastic Cloud endpoint
ELASTICSEARCH_API_KEY  — Elastic Cloud API key
```

---

## Data Flow (Single Request)

```
1. User types "What do students say about campus housing at Michigan?"
   on the Michigan tab

2. Browser POSTs to /api/ask:
   { "question": "What do students say about campus housing?",
     "school": "University of Michigan" }

3. server.py prepends filter:
   "[Filter to University of Michigan only] What do students say about campus housing?"

4. agent_mcp.py starts MCPClient:
   - Spawns mcp-server-elasticsearch subprocess
   - Handshakes over stdio JSON-RPC
   - Fetches available tools

5. Gemini 2.5 Flash receives question + tool definitions
   → Decides to search for housing-related content
   → Query: { school_tag: "umich", match: { comment: "housing dorm" }, size: 10 }

6. MCPClient sends tools/call to MCP subprocess
   → MCP server queries Elasticsearch
   → Returns mix of RMP comments + Reddit posts about housing

7. Gemini receives results from both sources
   → Synthesizes answer combining professor reviews and student Reddit discussions

8. Answer returned as JSON → displayed in chat UI
```

---

## Key Design Choices

**Why two data sources?**
Rate My Professors covers professor quality well but misses campus life entirely — housing, dining, social scene, mental health. Reddit subreddits fill that gap with authentic, unfiltered student discussions. Together they give a complete picture of the student experience.

**Why Reddit's public JSON API instead of PRAW?**
Reddit's `.json` endpoint (`reddit.com/r/<sub>.json`) requires zero credentials and works with a plain `requests.get()`. PRAW requires app registration and OAuth. The public API is sufficient for read-only collection and far simpler to operate.

**Why MCP instead of direct Elasticsearch SDK?**
The Elastic MCP server is an official Elastic tool and satisfies the hackathon's Elastic partner track requirement. It also lets Gemini express queries in natural language rather than requiring hand-crafted ES DSL.

**Why subprocess instead of MCP SDK?**
The official MCP Python SDK uses async I/O which conflicts with Flask's sync request handling. A direct JSON-RPC-over-stdio client is simpler, synchronous, and more reliable in a containerized environment.

**Why Flask instead of FastAPI/Streamlit?**
Flask gives full control over the HTML/CSS/JS frontend, which was needed to implement the custom university tab UI and chat bubble design.
