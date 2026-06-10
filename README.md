# CampusVoice 🎓

**AI-powered student sentiment agent for universities — built with Gemini + Elasticsearch + MCP**

CampusVoice aggregates real student reviews from Rate My Professors and College Confidential, indexes them in Elasticsearch, and lets administrators, counselors, and students ask plain-English questions to surface what's really happening on campus.

🌐 **Live App:** [campus-voice-agent-420887396772.us-east1.run.app](https://campus-voice-agent-420887396772.us-east1.run.app/)
💻 **GitHub:** [github.com/srivi19/campus-voice-agent](https://github.com/srivi19/campus-voice-agent)
🔍 **Powered by:** [Elastic Cloud](https://www.elastic.co/cloud)

---

## What It Does

Instead of manually reading hundreds of reviews, you can ask:

> *"What are students at UTK complaining about most?"*
> *"How does Vanderbilt compare to Georgia Tech for CS students?"*
> *"Which professors are most praised at UCLA?"*
> *"What do students say about workload at Duke?"*
> *"What do CS students say at Georgia Tech?"*

The agent searches real student reviews and forum discussions through the Elastic MCP server and synthesizes a structured, evidence-backed answer with real quotes.

---

## Universities Covered

UTK · Vanderbilt · Georgia Tech · University of Florida · University of Michigan · UCLA · Duke

---

## Data Sources

| Source | Type | Volume |
|--------|------|--------|
| [Rate My Professors](https://www.ratemyprofessors.com) | Professor ratings, course difficulty, teaching quality | 6,773 reviews |
| [College Confidential](https://talk.collegeconfidential.com) | Student forum discussions (2024+) | 6,419 posts |

**13,192 total reviews** across 7 universities covering academics, professor quality, grading, workload, and course difficulty.

---

## Who It's For

| User | Use Case |
|------|----------|
| School Administrators | Spot systemic problems before they become PR crises |
| College Counselors | Give prospective students honest, data-backed guidance |
| Prospective Students | Cut through the marketing and get real student sentiment |
| Department Heads | Identify teaching quality issues without waiting for surveys |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Google Gemini 2.5 Flash |
| Search & Storage | [Elasticsearch Serverless (Elastic Cloud)](https://www.elastic.co/cloud) |
| MCP Tool Layer | [@elastic/mcp-server-elasticsearch](https://github.com/elastic/mcp-server-elasticsearch) |
| Web Framework | Flask |
| Data Sources | Rate My Professors (GraphQL API), College Confidential (Discourse JSON API) |
| Deployment | Google Cloud Run (Docker) |
| Language | Python 3.11 |

---

## Project Structure

```
campus-voice-agent/
├── server.py                  # Flask API server — serves UI + /api/ask endpoint
├── agent_mcp.py               # Gemini agent + Elastic MCP client (core logic)
├── templates/
│   └── index.html             # Web UI with university tabs, chat, FAQ, tech stack
├── collect_rmp.py             # Collects professor reviews from Rate My Professors
├── collect_rmp_missing.py     # Targeted collector for schools missing data
├── collect_cc.py              # Collects forum posts from College Confidential (Discourse API)
├── setup_index.py             # Creates Elasticsearch index with mappings
├── ingest.py                  # Indexes all sources into Elasticsearch (with embeddings)
├── ingest_cc.py               # Fast keyword-only indexer for College Confidential posts
├── static/
│   └── architecture.pdf       # Tech stack & architecture diagram
├── Dockerfile                 # Cloud Run container (Python + Node + MCP server)
├── requirements.txt
├── .env                       # API keys (not committed)
└── data/
    ├── reviews.json           # RMP reviews
    └── cc_posts.json          # College Confidential posts (2024+)
```

---

## Architecture

See the [Tech Stack page](https://campus-voice-agent-420887396772.us-east1.run.app/) on the live app for a full diagram, or download [architecture.pdf](static/architecture.pdf).

---

## Local Setup

### 1. Prerequisites

- Python 3.11+
- Node.js 20+ (for the Elastic MCP server)
- Elastic Cloud account — [elastic.co/cloud](https://www.elastic.co/cloud)
- Gemini API key — [aistudio.google.com](https://aistudio.google.com/apikey)

### 2. Install dependencies

```bash
pip install -r requirements.txt
npm install -g @elastic/mcp-server-elasticsearch
```

### 3. Configure environment

Create a `.env` file:

```
GEMINI_API_KEY=your_gemini_api_key
ELASTICSEARCH_URL=your_elasticsearch_endpoint
ELASTICSEARCH_API_KEY=your_elasticsearch_api_key
```

### 4. Run the data pipeline (first time only)

```bash
# Collect professor reviews from Rate My Professors
python collect_rmp.py

# Collect forum posts from College Confidential (2024+)
python collect_cc.py

# Create the Elasticsearch index
python setup_index.py

# Index RMP reviews with embeddings
python ingest.py

# Index College Confidential posts (fast, no embeddings needed)
python ingest_cc.py
```

### 5. Start the web app

```bash
python server.py
# Open http://localhost:8080
```

---

## Cloud Deployment

The app deploys automatically to Google Cloud Run on every `git push` via Cloud Build.

```bash
git push  # triggers build + deploy
```

Environment variables (`GEMINI_API_KEY`, `ELASTICSEARCH_URL`, `ELASTICSEARCH_API_KEY`) are set directly in the Cloud Run service configuration.

---

## Hackathon

Built for the **Google Cloud Rapid Agent Hackathon** — *Building Agents for Real-World Challenges* (June 2026).

Partner track: **Elastic** — uses Elasticsearch as the data store and retrieval layer via the official Elastic MCP server.

---

## License

MIT License — see [LICENSE](LICENSE)
