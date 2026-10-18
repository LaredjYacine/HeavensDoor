# 🕊️ HeavensDoor

**HeavensDoor** is an AI-powered recruitment matching engine that connects **candidates** and **job postings** using a hybrid search + agentic reasoning pipeline. It combines vector similarity search, full-text (BM25) search, and a tool-using LLM agent (built with LangGraph) to understand vague or specific hiring queries and return relevant matches.

Jobs are kept fresh automatically: a scheduled pipeline ingests live remote postings from public job APIs and backfills their embeddings, so the agent always searches current data.

---

## ✨ Features

- **Agentic Job/Candidate Matching** — A LangGraph-based agent decides whether to run an exact keyword search, a hybrid semantic + BM25 search, a database schema lookup, or fall back to general Q&A, depending on how the user phrases their request.
- **Hybrid Search** — Combines dense vector embeddings (via `fastembed` / `BAAI/bge-small-en-v1.5`) with Postgres full-text search (BM25) over Supabase, merging both result sets for stronger recall.
- **Token-by-Token Streaming** — The `/v2` endpoints stream the agent's answer to the browser in real time over Server-Sent Events (SSE), backed by Redis Streams.
- **Live Job Ingestion** — A scheduled GitHub Action pulls fresh remote postings from **Himalayas** and **Jobicy**, normalizes them to the `Jobs` schema, generates embeddings, deduplicates, and inserts them into Supabase.
- **Incremental Embedding Backfill** — A standalone job embeds only the rows where `embeddings IS NULL`, so re-runs stay cheap.
- **Prompt Guardrails** — Incoming queries are screened by a **Llama Prompt Guard 2** model before reaching the agent; jailbreak / injection attempts are refused.
- **Conversation Memory & Caching** — Per-session memory (`MemorySaver`, keyed by `session_id`) plus a TTL node cache for repeated LLM calls.
- **Async Job Processing** — Requests are queued via **Celery** and backed by **Redis/Upstash**, so long-running agent calls don't block the API. Clients poll a `/result` endpoint (or stream from `/v2/result`) for completion.
- **Idempotent Requests** — Endpoints support an `idempotency_key` so retried/duplicate requests don't spawn duplicate jobs.
- **Resilient LLM Calls** — Automatic retries with exponential backoff (`tenacity`) around agent invocations, with a fallback to a secondary Groq model and a fine-tuned Gradio-hosted model if the primary agent hits a recursion limit or repeated failures.
- **Dead Letter Queue (DLQ)** — Failed jobs (after retries are exhausted) are pushed to a Redis DLQ (`dlq:agent` / `dlq:stream`) for later inspection instead of being silently dropped.
- **Rate Limiting** — API endpoints are protected with request-rate limits.
- **Simple Web Frontend** — A lightweight HTML/CSS/JS frontend (with a streaming chat UI and an About page) is served as static assets.

---

## 🏗️ Architecture

```
                         ┌─────────────────────────── FastAPI ───────────────────────────┐
User ── POST /agent ───► │ Celery task "agent"  ──► LangGraph agent (invoke)             │
     │                   │                                                            │
     └─ POST /v2/agent ─►│ Celery task "stream" ──► LangGraph agent (stream_events)      │
                         │                              │                             │
                         │                       Redis Stream (xadd tokens)            │
                         │                              │                             │
     GET /result ◄───────┤ poll Celery result      GET /v2/result ◄── SSE (xread)     │
                         └──────────────────────────────────────────────────────────┘
                                        │
                          ┌─────────────┴─────────────┐
                          ▼                           ▼
                  HybridRag Tool              matching_jobs /      get_tables /
                  (vector + BM25)             matching_candidates  table_schema
                          │                           │               │
                          └─────────────┬─────────────┴───────────────┘
                                        ▼
                              Supabase (Postgres + RPC)

GitHub Actions (scheduled):
  add_jobs.yml  ──► scripts/Jobs.py        ──► Himalayas / Jobicy APIs ──► Supabase Jobs
  embedding.yml ──► scripts/Embeddings.py  ──► fills NULL embeddings in Supabase Jobs
```

**Flow:**
1. Client submits a natural-language query to `POST /agent` (or streams via `POST /v2/agent`).
2. The request is deduplicated via an idempotency key, then dispatched as a Celery task.
3. The Celery worker invokes the LangGraph agent, which decides — based on the query — whether to:
   - Look up an **exact job title** (`matching_jobs`)
   - Look up **candidates by preferred role** (`matching_candidates`)
   - Run a **hybrid vector + keyword search** for vague/descriptive queries (`HybridRag`)
   - Inspect the database schema (`get_tables`, `table_schema`)
   - Answer general, non-database questions (`default_Answer`, via a fine-tuned fallback model)
4. The agent's final response is cached in Redis and returned to the client via `GET /result` or streamed via `GET /v2/result`.
5. If the agent fails repeatedly, the job is retried with backoff, then moved to a dead-letter queue.

**Data pipeline:**
- `add_jobs.yml` runs every 12 hours, fetching live postings from Himalayas and Jobicy and inserting new ones (deduplicated by description) into `Jobs`.
- `embedding.yml` backfills embeddings for any `Jobs` rows that are missing them.

---

## 🧰 Tech Stack

| Layer            | Technology |
|-------------------|------------|
| API Framework      | FastAPI |
| Agent Orchestration| LangGraph + LangChain |
| LLM Providers      | Groq (`ChatGroq`), Hugging Face Inference Endpoints |
| Prompt Guard       | Groq — Llama Prompt Guard 2 (`meta-llama/llama-prompt-guard-2-86m`) |
| Vector Embeddings  | fastembed (`BAAI/bge-small-en-v1.5`) |
| Database           | Supabase (Postgres + RPC functions for cosine similarity / FTS) |
| Task Queue         | Celery (`worker_pool="solo"` to fit small instances) |
| Cache / Broker     | Redis (Upstash) — also used for token streams, idempotency, and DLQ |
| Streaming          | Server-Sent Events (SSE) over Redis Streams |
| Fallback Model     | Gradio Client (hosted fine-tuned model) |
| Live Jobs          | Himalayas API + Jobicy API |
| Observability      | Langfuse (traces, generations, tool calls) |
| Evaluation         | DeepEval (faithfulness / answer relevancy) |
| Retry Logic        | Tenacity |
| CI/CD              | GitHub Actions |
| Package Manager    | uv |

---

## 📁 Project Structure

```
HeavensDoor/
├── .github/workflows/
│   ├── Fastapi_test.yml            # PR → main: run endpoint tests
│   ├── lint_test.yml               # PR → main: ruff format check + lint
│   ├── deploy.yml                  # push → main: deploy to Render
│   ├── add_jobs.yml                # scheduled: ingest live jobs (every 12h)
│   └── embedding.yml               # manual/scheduled: backfill embeddings
├── scripts/
│   ├── Jobs.py                     # live job ingestion (Himalayas + Jobicy)
│   └── Embeddings.py               # incremental embedding backfill
├── src/heavensdoor/
│   ├── __init__.py
│   └── app/
│       ├── main.py                     # FastAPI app entrypoint
│       ├── routes/
│       │   ├── Apiagent.py             # /agent and /result endpoints (polling)
│       │   ├── StreamingApi.py         # /v2/agent and /v2/result endpoints (SSE)
│       │   ├── background_Process.py   # Celery "agent" task
│       │   └── Stream_Process.py       # Celery "stream" task
│       ├── services/
│       │   ├── agent.py                # LangGraph graph assembly (memory + cache)
│       │   ├── agent_models.py         # LLM + graph node/state definitions
│       │   ├── celery.py               # Celery app configuration
│       │   ├── credentials.py          # Env var / client loading
│       │   ├── Current_job_Fetcher.py  # (placeholder) live-job fetching helper
│       │   ├── embedmodel.py           # Lazy singleton embedding model
│       │   ├── Logger.py               # Custom LangChain callback logger
│       │   ├── PromptModel.py          # Prompt Guard evaluation model
│       │   ├── Search_function.py      # Hybrid (vector + BM25) search logic
│       │   ├── SSL_fix.py              # SSL / fallback model client setup
│       │   ├── langfuse_setup.py       # Langfuse trace context helper
│       │   ├── limiter.py              # Rate limiter configuration
│       │   └── tools.py                # LangChain tool definitions for the agent
│       └── static/
│           ├── Front.html              # Chat UI
│           ├── Front.css
│           ├── Streaming.js            # Streaming chat client (SSE + markdown)
│           ├── About.html              # About page
│           ├── About.css
│           ├── script.js
│           ├── icon.png
│           ├── wallhaven-p8wo7p.jpg
│           └── ChatGPT_Image_...png
├── tests/
│   ├── conftest.py                     # Hermetic fixtures (fake Redis/Celery/Supabase)
│   ├── test_endpoints.py               # Endpoint tests
│   ├── _test_RagEval.py                # DeepEval RAG evaluation (live)
│   └── GoldenTestCase.json             # Golden dataset for RAG eval
├── docs.md
├── docs/scaling_10users.md
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
  - A `Jobs` table — base columns `job_name`, `skill_requirement`, `work_type`, `role`, `company`, plus `job_description`, `embeddings`, and the pipeline columns `salary` and `Expired_at`
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

# Backend URL (injected into the frontend as __BACKEND_URL__)
backendurl=http://localhost:8000

# Observability (optional - Langfuse tracing)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

> `upstash_redis`'s `Redis.from_env()` reads `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` specifically — make sure those are set in addition to `redisurl`.

> Tracing is skipped entirely when `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` are missing, so the app runs fine without a Langfuse project.

> The scheduled data jobs (`add_jobs.yml`, `embedding.yml`) only need `supabase_url` and `supabase_Key`, which are supplied from the `SUPABASE_URL` / `SUPABASE_KEY` GitHub secrets.

---

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/HeavensDoor.git
cd HeavensDoor

# Install dependencies with uv
uv sync

# (optional) install dev/test dependencies
uv sync --group dev
```

---

## ▶️ Running the Project

You'll need three processes running: the API server, the Celery worker, and Redis.

**1. Start the FastAPI server**
```bash
uv run uvicorn heavensdoor.app.main:app --reload
```

**2. Start the Celery worker**

The same worker handles both the `agent` (polling) and `stream` (SSE) tasks:
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
| `session_id` | string | ❌ | Conversation/memory thread identifier |

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

### `POST /v2/agent` (streaming)

Submit a query for a streamed response. Accepts a JSON body.

**Body:**
```json
{
  "query": "find me a remote frontend role",
  "session_id": "optional-thread-id",
  "idempotency_key": "optional-key"
}
```

**Response:**
```json
{
  "Status": "202 Accepted",
  "job_id": "celery-task-id",
  "idempotency_key": "generated-or-provided-uuid",
  "message": "Task submitted successfully."
}
```

### `GET /v2/result` (streaming)

Consume the agent's output as a **Server-Sent Events** stream.

| Param | Type | Required | Description |
|---|---|---|---|
| `job_id` | string | ✅ | The job ID returned by `/v2/agent` |

Emits newline-delimited SSE events, one token at a time:
```
data: {"token": "Hello", "done": false}

data: {"token": " world", "done": false}

data: {"token": "", "done": true}
```

If the Redis stream is not available yet, the endpoint reports `PENDING`; otherwise it falls back to the cached Celery result.

### `GET /` and `GET /about`

Serve the chat frontend and the About page respectively.

---

## 🧠 Agent Tools

| Tool | Purpose |
|---|---|
| `matching_jobs` | Exact/keyword search by job title (optionally filtered by `job_type`) |
| `matching_candidates` | Search candidates by preferred job role |
| `HybridRag` | Vector + BM25 hybrid search for vague/descriptive queries |
| `get_tables` | Lists all database tables |
| `table_schema` | Returns a table's schema/columns |
| `default_Answer` | General Q&A fallback (non-database questions), served by a fine-tuned model |

---

## 🔄 Data Pipeline

### Live job ingestion — `scripts/Jobs.py`

Run by `.github/workflows/add_jobs.yml` every 12 hours (and on demand):

- Fetches remote postings from the **Himalayas** API (`country=dz&worldwide=true&sort=recent`) and the **Jobicy** API (`count=200&geo=anywhere`).
- Normalizes each posting to the `Jobs` schema (`job_name`, `role`, `company`, `work_type`, `salary`, `skill_requirement`, `job_description`), computes its embedding, and records an `Expired_at` timestamp.
- Skips duplicates by checking the `job_description` before inserting.

### Embedding backfill — `scripts/Embeddings.py`

Run by `.github/workflows/embedding.yml`:

- Selects only `Jobs` rows where `embeddings IS NULL`.
- Embeds each `job_description` with `BAAI/bge-small-en-v1.5` and updates the row in place.

Both scripts are self-contained: they load `.env`, build their own Supabase client from `supabase_url` / `supabase_Key`, and reuse the lazy singleton in `services/embedmodel.py`.

---

## 🖥️ Frontend

A static frontend is served from `src/heavensdoor/app/static/`:

- **Chat UI** (`Front.html`, `Front.css`, `Streaming.js`) — streams tokens from `/v2/result`, renders Markdown with `marked`, includes a typing animation, a stop/abort flow, auto-scroll, and a per-browser `session_id` stored in `localStorage`.
- **About page** (`About.html`, `About.css`) — served at `/about`.

The backend URL is injected at render time by replacing the `__BACKEND_URL__` placeholder in `Front.html` with the value of the `backendurl` env var.

Live demo: https://heavensdoor.onrender.com/

---

## 🧪 Testing & Evaluation

```bash
# Run the hermetic endpoint suite
uv run pytest -v

# Lint / format
uv run ruff check .
uv run ruff format --check .
```

- `tests/conftest.py` keeps the suite hermetic: it sets dummy credentials and replaces Redis, Celery, and the Supabase client with in-memory fakes, so no external service is contacted in CI.
- `tests/test_endpoints.py` covers the pages, static assets, and the `/agent` + `/result` endpoints.
- `tests/_test_RagEval.py` runs a **DeepEval** evaluation (Faithfulness + Answer Relevancy, judged by a Groq model) against `tests/GoldenTestCase.json`. It requires network access and real credentials and enforces a regression gate (fails if the success rate drops below the baseline).

---

## 🔁 CI/CD

| Workflow | Trigger | Purpose |
|---|---|---|
| `Fastapi_test.yml` | Pull request → `main` | `uv sync --group dev` + `pytest -v` |
| `lint_test.yml` | Pull request → `main` | `ruff format --check .` + `ruff check .` |
| `deploy.yml` | Push → `main` | Deploy to Render (`johnbeynon/render-deploy-action`) |
| `add_jobs.yml` | Schedule (every 12h) / manual | Ingests live jobs into Supabase |
| `embedding.yml` | Manual | Backfills missing job embeddings |

Deployment requires the `SERVICE_ID` and `RENDER_API_KEY` secrets; the data jobs require `SUPABASE_URL` and `SUPABASE_KEY`.

---

## 📝 License

See [LICENSE](./LICENSE) for details.

---

## 🤝 Contributing

Issues and pull requests are welcome. Please open an issue first to discuss significant changes.
