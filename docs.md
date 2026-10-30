# HeavensDoor — Job & Candidate Matching Agent

HeavensDoor is a job and candidate matching platform built with FastAPI, LangGraph, Celery, Supabase, Upstash Redis, and Groq. It exposes two API versions (v1 and v2) for submitting job/candidate queries asynchronously, with optional streaming results via Server-Sent Events (SSE).

---

## Table of Contents

1. [Tech Stack](#tech-stack)
2. [Project Structure](#project-structure)
3. [Environment Variables](#environment-variables)
4. [Installation](#installation)
5. [Running the Project](#running-the-project)
6. [API Reference](#api-reference)
   - [GET /](#get-)
   - [GET /about](#get-about)
   - [POST /agent](#post-agent-v1)
   - [GET /result](#get-result-v1)
   - [POST /v2/agent](#post-v2agent-v2-streaming)
   - [GET /v2/result](#get-v2result-v2-streaming)
7. [Data Pipeline](#data-pipeline)
8. [Agent Tools](#agent-tools)
9. [Testing & Evaluation](#testing--evaluation)
10. [Rate Limiting](#rate-limiting)
11. [Error Handling & Dead Letter Queue](#error-handling--dead-letter-queue)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Web Framework | FastAPI |
| Background Jobs | Celery + Upstash Redis (broker & backend) |
| Agent Framework | LangGraph + LangChain |
| LLM | Groq (Qwen, GPT-OSS, Llama Prompt Guard) |
| Vector Store / Database | Supabase (PostgreSQL + pgvector + Full-Text Search) |
| Embeddings | fastembed (BAAI/bge-small-en-v1.5) |
| Streaming / Idempotency | Upstash Redis (Streams) |
| Tracing | Langfuse |
| Rate Limiting | slowapi |
| Frontend | HTML/CSS/JS (static files served by FastAPI) |

---

## Project Structure

```
HeavensDoor/
├── pyproject.toml          # Project metadata & dependencies
├── requirements.txt        # Pip installable dependencies
├── .env.example            # Environment variable template
├── .env                    # Local secrets (not committed)
├── README.md
├── docs.md                 # This file
├── agent_trace.jsonl       # Local LLM trace log
├── src/
│   └── heavensdoor/
│       ├── __init__.py
│       ├── app/
│       │   ├── __init__.py
│       │   ├── main.py                 # FastAPI app entrypoint
│       │   ├── limiter.py              # slowapi rate limiter
│       │   ├── static/                 # Frontend HTML/CSS/JS
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   ├── Apiagent.py         # v1 endpoints (/agent, /result)
│       │   │   ├── StreamingApi.py     # v2 endpoints (/v2/agent, /v2/result)
│       │   │   ├── Stream_Process.py   # Celery task "stream" (v2)
│       │   │   └── background_Process.py # Celery task "agent" (v1)
│       │   └── services/
│       │       ├── __init__.py
│       │       ├── credentials.py      # Supabase, Groq, Redis env config
│       │       ├── agent.py            # LangGraph agent builder (llm + fallback)
│       │       ├── agent_models.py     # MessageState, graph nodes, tools
│       │       ├── celery.py           # Celery app config
│       │       ├── embedmodel.py       # Embedding model loader
│       │       ├── langfuse_setup.py   # Langfuse tracing context
│       │       ├── limiter.py          # Rate limiter instance
│       │       ├── Logger.py           # JSONL trace logger
│       │       ├── PromptModel.py      # Groq prompt-guard safety check
│       │       ├── Search_function.py  # Hybrid search (RAG + BM25 + RRF)
│       │       ├── SSL_fix.py          # Hugging Face Gradio client
│       │       └── tools.py            # (unused placeholder)
│       └── scripts/
│           ├── Jobs.py                 # Himalayas + Jobicy job ingestion
│           ├── Apify.py                # Emploitic scraper via Apify
│           └── Embeddings.py           # Embedding backfill for null vectors
└── tests/
    ├── conftest.py                     # Pytest fixtures & fakes
    ├── test_endpoints.py               # Endpoint tests (hermetic)
    ├── _test_RagEval.py                # RAG evaluation with deepeval
    └── GoldenTestCase.json             # Golden test cases
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values.

| Variable | Required | Description |
|----------|----------|-------------|
| `supabase_url` | Yes | Supabase project URL |
| `supabase_Key` | Yes | Supabase anon key |
| `service_role` | No | Supabase service role key |
| `groq` | Yes | Groq API key (read as `groq`, set as `GROQ_API_KEY`) |
| `redisurl` | Yes | Redis URL for Celery broker/backend |
| `backendurl` | Yes | Backend URL injected into frontend HTML |
| `UPSTASH_REDIS_REST_URL` | Yes | Upstash Redis REST URL |
| `UPSTASH_REDIS_REST_TOKEN` | Yes | Upstash Redis REST token |
| `LANGFUSE_PUBLIC_KEY` | No | Langfuse public key (tracing) |
| `LANGFUSE_SECRET_KEY` | No | Langfuse secret key (tracing) |
| `hf_token` | No | Hugging Face token (fine-tuned fallback model) |
| `Test_Key` | No | Test Groq key (RAG eval) |
| `Test_Key2` | No | Test Groq judge key (RAG eval) |
| `APIFY_TOKEN` / `ampify` | No | Apify API token (Emploitic scraper) |

---

## Installation

```bash
# Clone the repository
cd HeavensDoor

# Create virtual environment (Python 3.11+)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Or with uv
uv sync

# Set up environment
cp .env.example .env
# Edit .env with your credentials
```

---

## Running the Project

### Start the FastAPI server

```bash
uvicorn heavensdoor.app.main:app --reload
```

Or run the module directly:

```bash
python -m heavensdoor
```

### Start the Celery worker

Celery is required for background job processing. Run in a separate terminal:

```bash
celery -A heavensdoor.app.services.celery.celery_app worker --pool=solo --loglevel=info
```

> **Note:** `worker_pool="solo"` is hardcoded to avoid RAM exhaustion on Render's free tier. Do not change to `prefork` unless you have sufficient memory.

### Start Celery Beat (optional)

If you schedule periodic tasks (e.g., job expiration cleanup), run:

```bash
celery -A heavensdoor.app.services.celery.celery_app beat --loglevel=info
```

---

## API Reference

### Base URL

- Local: `http://localhost:8000`
- Production: your Render/Railway domain

---

### GET /

Serves the frontend chat interface (`Front.html`). Replaces `__BACKEND_URL__` with the `backendurl` environment variable.

**Response:** `text/html`

---

### GET /about

Serves the about page (`About.html`).

**Response:** `text/html`

---

### POST /agent (v1)

Submit a job/candidate query. Returns a `job_id` for polling.

**Request:** Query parameters (form data)

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | The user's job/candidate search query |
| `idempotency_id` | string | No | Client-generated idempotency key (auto-generated if omitted) |
| `session_id` | string | No | Conversation session ID for LangGraph memory |

**Example:**

```bash
curl -X POST "http://localhost:8000/agent?query=frontend%20developer&session_id=sess-1"
```

**Response (200):**

```json
{
  "job_id": "celery-task-id",
  "status": "202 Accepted",
  "idempotency_key": "uuid-or-client-key",
  "message": "job Submitted go to /result "
}
```

**Response (Duplicate):**

```json
{
  "status": "Duplicate",
  "job_id": "existing-job-id",
  "idempotency_id": "dup-key",
  "message": "Job already submitted before"
}
```

**Rate Limit:** `1000/minute` per IP.

---

### GET /result (v1)

Poll for the result of a v1 job.

**Request:** Query parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | string | Yes | Celery task ID returned from `/agent` |

**Example:**

```bash
curl "http://localhost:8000/result?job_id=celery-task-id"
```

**Response (Pending):**

```json
{
  "job_id": "celery-task-id",
  "state": "PENDING",
  "result": null,
  "message": "Task is still in progress."
}
```

**Response (Success):**

```json
{
  "job_id": "celery-task-id",
  "state": "SUCCESS",
  "result": ["Senior Frontend Engineer", "..."]
}
```

**Response (Cached):**

If the result was previously cached in Redis, it returns the cached JSON directly.

**Rate Limit:** `1000/minute` per IP.

---

### POST /v2/agent (v2 Streaming)

Submit a job/candidate query via JSON body. Starts a Celery task that streams tokens to Redis.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | The user's query |
| `session_id` | string | No | Conversation session ID |
| `idempotency_key` | string | No | Client-generated idempotency key |

**Example:**

```bash
curl -X POST "http://localhost:8000/v2/agent" \
  -H "Content-Type: application/json" \
  -d '{"query": "frontend developer", "session_id": "sess-1"}'
```

**Response (200):**

```json
{
  "Status": "202 Accepted",
  "job_id": "celery-task-id",
  "idempotency_key": "uuid-or-client-key",
  "message": "Task submitted successfully."
}
```

**Response (Duplicate):**

```json
{
  "Status": "Duplicate",
  "job_id": "existing-job-id",
  "idempotency_key": "dup-key",
  "message": "Duplicate request. Job is already in progress."
}
```

**Rate Limit:** `1000/minute` per IP.

---

### GET /v2/result (v2 Streaming)

Poll for v2 results. If Redis stream entries exist for the `job_id`, returns a Server-Sent Events (SSE) stream. Otherwise falls back to Celery result polling.

**Request:** Query parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `job_id` | string | Yes | Celery task ID returned from `/v2/agent` |

**Example (SSE stream):**

```bash
curl -N "http://localhost:8000/v2/result?job_id=celery-task-id"
```

**SSE Event Format:**

```
data: {"token": "Hel", "done": false}

data: {"token": "lo", "done": false}

data: {"token": "[DONE]", "done": true}
```

**Response (Non-stream, Pending/Success):**

```json
{
  "status": "202 Accepted",
  "job_id": "celery-task-id",
  "result": ["Senior Frontend Engineer"]
}
```

```json
{
  "status": "PENDING",
  "job_id": "celery-task-id",
  "message": "Task is still in progress."
}
```

**Rate Limit:** `1000/minute` per IP.

---

## Data Pipeline

### Live Job Ingestion — `scripts/Jobs.py`

Fetches jobs from:
- **Himalayas API** (`https://himalayas.app/jobs/api/search?country=dz&worldwide=true&sort=recent`)
- **Jobicy API** (`https://jobicy.com/api/v2/remote-jobs?count=200&geo=anywhere`)

For each job, it:
1. Checks for duplicates by `job_description`
2. Generates embeddings via `fastembed`
3. Inserts into Supabase `Jobs` table

Run manually:

```bash
python scripts/Jobs.py
```

### Embedding Backfill — `scripts/Embeddings.py`

Backfills `embeddings` for existing jobs that have `NULL` vectors.

Run manually:

```bash
python scripts/Embeddings.py
```

### Apify Scraping — `scripts/Apify.py`

Scrapes Emploitic job listings via Apify actor `scraper_guru/algeria-emploitic-jobs-scraper`, maps fields to the Supabase `Jobs` schema, checks for duplicates, generates embeddings, and inserts.

Run with an Apify run ID:

```bash
python scripts/Apify.py <apify_run_id>
```

---

## Agent Tools

The LangGraph agent has access to the following tools (defined in `src/heavensdoor/app/services/agent_models.py`):

| Tool | Description |
|------|-------------|
| `HybridRag` | Hybrid search (vector + BM25 + RRF) over the `Jobs` table. Accepts optional filters: `work_type`, `company`, `role`. Returns up to 5 matches. |
| `matching_candidates` | Searches the `Candidates` table by `prefered_job_role` (ILIKE). |
| `get_tables` | Lists all tables in the database via Supabase RPC. |
| `table_schema` | Returns the schema of a specific table via Supabase RPC. |
| `default_Answer` | Falls back to a fine-tuned Hugging Face model (Gradio client) for general advice. |

The agent uses a `MessageState` graph with nodes:
- `llm_calls` — decides whether to call a tool
- `tool_node` — executes tool calls
- Conditional edge: continue to `tool_node` if tools are called, otherwise `END`

A fallback graph (`fallback_model`) is used when the primary Groq model hits rate limits or errors.

---

## Testing & Evaluation

### Endpoint Tests

Hermetic tests using `TestClient` with faked Redis and Celery. No external services required.

```bash
pytest tests/test_endpoints.py -v
```

### RAG Evaluation

Uses `deepeval` with `FaithfulnessMetric` and `AnswerRelevancyMetric`. Requires real Supabase credentials and Groq API keys (`Test_Key`, `Test_Key2`). Skips if `.env` is missing credentials.

```bash
pytest tests/_test_RagEval.py -v
```

Golden test cases are stored in `tests/GoldenTestCase.json` (30 cases covering job search queries in English).

---

## Rate Limiting

Implemented via `slowapi` with `get_remote_address` as the key function.

| Endpoint | Limit |
|----------|-------|
| `POST /agent` | 1000/minute |
| `GET /result` | 1000/minute |
| `POST /v2/agent` | 1000/minute |
| `GET /v2/result` | 1000/minute |

Excess requests return `429 Too Many Requests`.

---

## Error Handling & Dead Letter Queue

Celery tasks (`stream` and `agent`) wrap execution in `try/except` blocks:

1. **Groq rate limits / API errors:** Retried up to 4 times with exponential backoff, then falls back to the secondary model.
2. **Graph recursion errors:** Falls back to the fine-tuned Hugging Face model.
3. **All other failures:** The error, prompt, and timestamp are pushed to a Redis dead letter queue:
   - `dlq:stream` for v2 tasks
   - `dlq:agent` for v1 tasks
4. **Temporarily at capacity / 503:** The Celery task retries itself with a countdown.

If all retries fail, the task returns:
```
"couldnt fulfill your request at the current time, please try again later"
```

---

## Notes

- **Conversation memory:** LangGraph uses `MemorySaver` (in-memory). Conversation history is keyed by `session_id`. If the server restarts, memory is lost unless you switch to a persistent checkpointer (e.g., `PostgresSaver`).
- **Embedding model:** Currently `BAAI/bge-small-en-v1.5` (English-only). French job descriptions may have degraded semantic search quality. BM25 keyword search still works for French.
- **Static files:** Served from `src/heavensdoor/app/static`. The path is relative; run the server from the project root.
- **Render free tier:** `worker_pool="solo"` is required to avoid OOM kills. Web services spin down after inactivity; the first request may be slow (cold start).
