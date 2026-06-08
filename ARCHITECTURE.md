# CampusVoice — Architecture

🌐 **Live:** [campus-voice-agent-420887396772.us-east1.run.app](https://campus-voice-agent-420887396772.us-east1.run.app/)
💻 **GitHub:** [github.com/srivi19/campus-voice-agent](https://github.com/srivi19/campus-voice-agent)

---

## Overview

CampusVoice is an agentic AI app that answers natural-language questions about university professors and campus life using real student review data. It combines a Gemini LLM with an Elasticsearch backend via the Model Context Protocol (MCP).

```
User → Flask API → Gemini Agent → Elastic MCP Server → Elasticsearch
                        ↑                                     |
                        └─────────── tool results ────────────┘
```

---

## Component Breakdown

### 1. Web UI (`templates/index.html`)
A single-page app served by Flask. Users select a university tab, type a question, and receive a streamed answer. Built with vanilla HTML/CSS/JS — no frontend framework needed.

- University tabs: UTK, Vanderbilt, Georgia Tech, UF, Michigan, UCLA, Duke
- Suggested questions per university
- University descriptions and emoji branding

### 2. Flask API Server (`server.py`)
Thin HTTP layer with two endpoints:

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

Key design decisions:
- **No aggregation queries** — the MCP server returns 0 results for agg-only queries; Gemini is instructed to use sorted searches instead
- **Thinking disabled** — `thinking_budget=0` prevents Gemini 2.5 Flash from returning empty thought-only responses
- **85-second time budget** — hard wall-clock limit to prevent Cloud Run 300s timeout
- **503 retry with backoff** — 5 attempts at 3s, 6s, 9s, 12s intervals for Gemini API overload

### 4. MCP Client (inside `agent_mcp.py`)
A lightweight JSON-RPC over stdio client that:

1. Spawns `@elastic/mcp-server-elasticsearch` as a subprocess
2. Performs the MCP handshake (`initialize` → `notifications/initialized`)
3. Lists available tools (`tools/list`)
4. Calls tools on Gemini's behalf (`tools/call`)
5. Filters stdout for valid JSON-RPC lines (ignores Node.js telemetry noise)

The MCP server handles all Elasticsearch query construction — Gemini describes what it wants in natural language and the MCP server translates it to ES DSL.

### 5. Elastic MCP Server (subprocess)
`@elastic/mcp-server-elasticsearch` — an official Elastic npm package that:

- Connects to Elasticsearch Cloud using `ES_URL` + `ES_API_KEY`
- Exposes search, get, and index tools over MCP stdio
- Runs inside the same Docker container as the Python app

### 6. Elasticsearch (`campus_reviews` index)
Hosted on [Elastic Cloud Serverless](https://www.elastic.co/cloud). Stores ~25,000 professor reviews with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `school` | keyword | Full university name |
| `school_tag` | keyword | Short tag (utk, vanderbilt, etc.) |
| `professor_name` | text | Professor full name |
| `department` | keyword | Academic department |
| `course` | keyword | Course code |
| `comment` | text | Full student review text |
| `helpful_rating` | float | 1–5 helpfulness score |
| `clarity_rating` | float | 1–5 clarity score |
| `difficulty_rating` | float | 1–5 difficulty score |
| `avg_rating` | float | Professor's overall average rating |
| `category` | keyword | Auto-tagged: academics, housing, dining, etc. |
| `date` | date | Review date |

### 7. Data Pipeline
One-time setup scripts:

- **`collect_rmp.py`** — GraphQL scraper for Rate My Professors. Fetches up to 50 professors × 15 reviews per university across 7 schools.
- **`setup_index.py`** — Creates the `campus_reviews` index with field mappings.
- **`ingest.py`** — Bulk-indexes the collected reviews into Elasticsearch.

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
1. User types "Which professors are most praised at Vanderbilt?"
   in the web UI (Michigan tab filtered to vanderbilt school_tag)

2. Browser POSTs to /api/ask:
   { "question": "Which professors are most praised?",
     "school": "Vanderbilt University" }

3. server.py prepends filter:
   "[Filter to Vanderbilt University only] Which professors are most praised?"

4. agent_mcp.py starts MCPClient:
   - Spawns mcp-server-elasticsearch subprocess
   - Handshakes over stdio JSON-RPC
   - Fetches available tools

5. Gemini 2.5 Flash receives question + tool definitions
   → Decides to call: elasticsearch_search
   → Query: { school_tag: "vanderbilt", sort: avg_rating desc, size: 50 }

6. MCPClient sends tools/call to MCP subprocess
   → MCP server queries Elasticsearch
   → Returns top 50 reviews sorted by rating

7. Gemini receives search results
   → Synthesizes answer: names top professors, quotes reviews, cites ratings

8. Answer returned as JSON → displayed in chat UI
```

---

## Key Design Choices

**Why MCP instead of direct Elasticsearch SDK?**
The Elastic MCP server is an official Elastic tool and satisfies the hackathon's Elastic partner track requirement. It also lets Gemini express queries in natural language rather than requiring hand-crafted ES DSL.

**Why subprocess instead of MCP SDK?**
The official MCP Python SDK uses async I/O which conflicts with Flask's sync request handling. A direct JSON-RPC-over-stdio client is simpler, synchronous, and more reliable in a containerized environment.

**Why Flask instead of FastAPI/Streamlit?**
Flask gives full control over the HTML/CSS/JS frontend, which was needed to implement the custom university tab UI and chat bubble design.

**Why disable Gemini thinking?**
Gemini 2.5 Flash's thinking mode (`thinking_budget > 0`) sometimes returns responses where all parts are internal thought tokens with no text or function calls, causing the agent loop to stall. Setting `thinking_budget=0` produces reliable, predictable outputs.
