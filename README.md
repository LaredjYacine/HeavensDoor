# 🕊️ HeavensDoor

**HeavensDoor** is an AI-powered recruitment matching engine that connects **candidates** and **job postings** using a hybrid search + agentic reasoning pipeline. It combines vector similarity search, full-text (BM25) search, and a tool-using LLM agent (built with LangGraph) to understand vague or specific hiring queries and return relevant matches.

---

## ✨ Features

- **Agentic Job/Candidate Matching** — A LangGraph-based agent decides whether to run an exact keyword search, a hybrid semantic + BM25 search, a database schema lookup, or fall back to general Q&A, depending on how the user phrases their request.
- **Hybrid Search** — Combines dense vector embeddings (via `fastembed` / `BAAI/bge-small-en-v1.5`) with Postgres full-text search (BM25) over Supabase, merging both result sets for stronger recall.
- **Async Job Processing** — Requests are queued via **Celery** and backed by **Redis/Upstash**, so long-running agent calls don't block the API. Clients poll a `/result` endpoint for completion.
- **Idempotent Requests** — The `/agent` endpoint supports an `idempotency_id` so retried/duplicate requests don't spawn duplicate jobs.
- **Resilient LLM Calls** — Automatic retries with exponential backoff (`tenacity`) around agent invocations, with a fallback to a fine-tuned Gradio-hosted model if the primary agent hits a recursion limit or repeated failures.
- **Dead Letter Queue (DLQ)** — Failed jobs (after retries are exhausted) are pushed to a Redis DLQ (`dlq:agent`) for later inspection instead of being silently dropped.
- **Rate Limiting** — API endpoints are protected with request-rate limits.
- **Simple Web Frontend** — A lightweight HTML/CSS/JS frontend is served as static assets.

---

## 🏗️ Architecture

```
User → FastAPI (/agent) → Celery task queue → LangGraph Agent
                                                    │
                                    ┌───────────────┼────────────────┐
                                    ▼               ▼                ▼
                            HybridRag Tool   matching_jobs /   get_tables /
                            (vector + BM25)  matching_candidates table_schema
                                    │               │                │
                                    └───────────────┴────────────────┘
                                                    ▼
                                            Supabase (Postgres)

User polls FastAPI (/result) → Redis (job status/result cache) → Response
```

**Flow:**
1. Client submits a natural-language query to `POST /agent`.
2. The request is deduplicated via an idempotency key, then dispatched as a Celery task.
3. The Celery worker invokes the LangGraph agent, which decides — based on the query — whether to:
   - Look up an **exact job title** (`matching_jobs`)
   - Look up **candidates by preferred role** (`matching_candidates`)
   - Run a **hybrid vector + keyword search** for vague/descriptive queries (`HybridRag`)
   - Inspect the database schema (`get_tables`, `table_schema`)
   - Answer general, non-database questions (`default_Answer`, via a fine-tuned fallback model)
4. The agent's final response is cached in Redis and returned to the client via `GET /result`.
5. If the agent fails repeatedly, the job is retried with backoff, then moved to a dead-letter queue.

---

## 🧰 Tech Stack

| Layer            | Technology |
|-------------------|------------|
| API Framework      | FastAPI |
| Agent Orchestration| LangGraph + LangChain |
| LLM Providers      | Groq (`ChatGroq`), Hugging Face Inference Endpoints |
| Vector Embeddings  | fastembed (`BAAI/bge-small-en-v1.5`) |
| Database           | Supabase (Postgres + RPC functions for cosine similarity / FTS) |
| Task Queue         | Celery |
| Cache / Broker     | Redis (Upstash) |
| Fallback Model     | Gradio Client (hosted fine-tuned model) |
| Observability      | Langfuse (traces, generations, tool calls) |
| Retry Logic        | Tenacity |
| Package Manager    | uv |

---

## 📁 Project Structure

```
HeavensDoor/
├── src/heavensdoor/
│   ├── __init__.py
│   └── app/
│       ├── main.py                     # FastAPI app entrypoint
│       ├── routes/
│       │   ├── Apiagent.py             # /agent and /result endpoints
│       │   └── background_Process.py   # Celery task definition
│       ├── services/
│       │   ├── Embeddings.py           # Embedding utilities
│       │   ├── Logger.py               # Custom LangChain callback logger
│       │   ├── SSL_fix.py              # SSL / fallback model client setup
│       │   ├── Search_function.py      # Hybrid (vector + BM25) search logic
│       │   ├── agent.py                # LangGraph graph assembly
│       │   ├── agent_models.py         # LLM + graph node/state definitions
│       │   ├── celery.py               # Celery app configuration
│       │   ├── credentials.py          # Env var / client loading
│       │   ├── langfuse_setup.py       # Langfuse trace context helper
│       │   ├── limiter.py              # Rate limiter configuration
│       │   └── tools.py                # LangChain tool definitions for the agent
│       └── static/
│           ├── Front.html
│           ├── Front.css
│           └── script.js
├── pyproject.toml
├── uv.lock
├── .python-version
└── LICENSE
```

---

## ⚙️ Prerequisites

- Python (version pinned in `.python-version`)
- [uv](https://docs.astral.sh/uv/) for dependency management
- A [Supabase](https://supabase.com) project with:
  - A `Jobs` table (`job_name`, `skill_requirement`, `work_type`, `role`, `company`)
  - A `Candidates` table (`prefered_job_role`, `skills`, `degrees`)
  - RPC functions: `cosine_similarity`, `search_jobs_fts`, `get_tables`, `get_table_schema`
- A Redis instance (this project uses [Upstash](https://upstash.com))
- API keys for [Groq](https://console.groq.com) and/or [Hugging Face](https://huggingface.co/settings/tokens)

---

## 🔑 Environment Variables

Create a `.env` file in the project root:

```env
# Supabase
supabase_url=your_supabase_project_url
supabase_Key=your_supabase_anon_or_service_key
service_role=your_supabase_service_role_key

# LLM Providers
groq=your_groq_api_key
hf_token=your_huggingface_token

# Redis / Celery
redisurl=your_redis_connection_url
UPSTASH_REDIS_REST_URL=your_upstash_rest_url
UPSTASH_REDIS_REST_TOKEN=your_upstash_rest_token

# Observability (optional - Langfuse tracing)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

> `upstash_redis`'s `Redis.from_env()` reads `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` specifically — make sure those are set in addition to `redisurl`.

> Tracing is skipped entirely when `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` are missing, so the app runs fine without a Langfuse project.

---

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/HeavensDoor.git
cd HeavensDoor

# Install dependencies with uv
uv sync
```

---

## ▶️ Running the Project

You'll need three processes running: the API server, the Celery worker, and Redis.

**1. Start the FastAPI server**
```bash
uv run uvicorn heavensdoor.app.main:app --reload
```

**2. Start the Celery worker**
```bash
uv run celery -A heavensdoor.app.services.celery worker --loglevel=info
```

**3. Redis**

Make sure your Redis/Upstash instance is reachable via the credentials in `.env`.

Once running, open the frontend at the root URL served by FastAPI's static files, or interact directly with the API.

---

## 📡 API Reference

### `POST /agent`

Submit a natural-language recruitment query for async processing.

**Query Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `query` | string | ✅ | The user's request (e.g., *"find me a remote frontend role"*) |
| `idempotency_id` | string | ❌ | Optional key to prevent duplicate job submission |

**Response:**
```json
{
  "job_id": "celery-task-id",
  "status": "202 Accepted",
  "idempotency_key": "generated-or-provided-uuid",
  "message": "job Submitted go to /result "
}
```

### `GET /result`

Poll for the result of a previously submitted job.

**Query Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `job_id` | string | ✅ | The job ID returned by `/agent` |

**Response:**
```json
{
  "job_id": "celery-task-id",
  "state": "SUCCESS | PENDING | FAILURE",
  "result": "..."
}
```

---

## 🧠 Agent Tools

| Tool | Purpose |
|---|---|
| `matching_jobs` | Exact/keyword search by job title |
| `matching_candidates` | Search candidates by preferred job role |
| `HybridRag` | Vector + BM25 hybrid search for vague/descriptive queries |
| `get_tables` | Lists all database tables |
| `table_schema` | Returns a table's schema/columns |
| `default_Answer` | General Q&A fallback (non-database questions), served by a fine-tuned model |

---

## 🖥️ Frontend

A minimal static frontend (`Front.html`, `Front.css`, `script.js`) is included under `src/heavensdoor/app/static/` for interacting with the API directly from the browser.

Link : https://heavensdoor.onrender.com/

---

## 📝 License

See [LICENSE](./LICENSE) for details.

---

## 🤝 Contributing

Issues and pull requests are welcome. Please open an issue first to discuss significant changes.
