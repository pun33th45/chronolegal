# ChronoLegal — Presentation Day Local Demo Guide

A Docker-free way to run ChronoLegal reliably for tomorrow's presentation.
Docker Desktop is not installed on this machine (confirmed), so this uses
the backend's Python virtual environment directly and Vite's dev server —
not `docker compose`, `make dev`, or any cloud deployment. Nothing here
changes the application; it's the same code the automated test suite and
CI already exercise.

## Architecture being demonstrated

```
React/Vite frontend (npm run dev, localhost:5173)
        |
        v
FastAPI backend (uvicorn, localhost:8000)
        |
        +--> RAG pipeline: query rewrite -> embed -> Chroma retrieval
        |    -> [BM25 hybrid fusion] -> rerank -> similarity threshold
        |    -> grounded prompt -> Groq
        |
        +--> Embedded Chroma (in-process, local disk)
        |
        +--> Supabase PostgreSQL (case data, users, conversations)
```

## Prerequisites

- `backend/.venv` already set up (it is — confirmed working throughout this
  project's test runs).
- `frontend/node_modules` already installed (confirmed).
- A real Supabase **Session Pooler** connection (not Direct Connection —
  see `docs/deployment.md`'s Supabase section for why) and a real Groq API
  key. **Neither is filled in below yet — see the note at the end of this
  file.**

## 1. Configure the backend environment

Create `backend/.env` (already gitignored — never commit this file) with:

```env
APP_ENV=development
DEBUG=false
SECRET_KEY=any-random-string-for-tonight
JWT_SECRET_KEY=any-random-string-for-tonight

POSTGRES_HOST=<Supabase Session Pooler host, e.g. aws-0-<region>.pooler.supabase.com>
POSTGRES_PORT=5432
POSTGRES_DB=postgres
POSTGRES_USER=postgres.<your-project-ref>
POSTGRES_PASSWORD=<your real Supabase password>

CHROMA_MODE=embedded
CHROMA_PERSIST_DIRECTORY=./chroma_data

EMBEDDING_PROVIDER=huggingface
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

LLM_PROVIDER=groq
GROQ_API_KEY=<your real Groq key>
GROQ_MODEL=llama-3.1-8b-instant

CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
CORS_ALLOW_CREDENTIALS=true
```

`APP_ENV=development` (not `production`) is deliberate for tonight: it
skips the production-secrets validator entirely, so a quick random
`SECRET_KEY` is fine and nothing can accidentally block startup a few hours
before the presentation. Switch to `production` only if you also set real
generated secrets.

If Supabase requires the SQL-extension step, run once in Supabase's SQL
Editor (harmless if already applied):

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
```

## 2. Start the backend

```
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Watch the startup logs for, in order: `Database migrations applied` →
`Demo mode: seeded sample legal cases` (first run only) → `Demo mode:
embedded Chroma collection is empty — re-embedding sample cases` (first run
only) → `Embedding model warmed up` → `Redis not available: ...` (expected
and harmless — Redis isn't used for this demo) → server ready on port 8000.

In a second terminal, confirm:

```
curl http://localhost:8000/health
```

## 3. Start the frontend

```
cd frontend
npm run dev
```

Open `http://localhost:5173`. Vite's dev proxy (already configured in
`vite.config.ts`) forwards `/api` to `localhost:8000`, so no
`VITE_API_BASE_URL` override is needed for this local run.

## 4. How the knowledge base initializes

Nothing to do manually. On first backend startup, `_ensure_demo_data_ready()`
(`backend/app/main.py`) seeds the six sample landmark cases into Postgres
if empty, then embeds them into Chroma if the vector collection is empty.
On any later restart, if the local `chroma_data` folder is still present,
this is skipped (fast startup); if it was deleted, it re-embeds
automatically — nothing to fix, this is the same ephemeral-storage recovery
mechanism built and tested for the hosted deployment.

## 5. Demo questions

See `DEMO_QUESTIONS.md` at the repo root — five questions mapped to
specific seeded cases, plus one deliberately unrelated question to show the
insufficient-evidence fallback instead of a hallucinated answer.

## 6. What to show the judges, in order

1. Register/login (or use an already-registered account).
2. Ask one of the five case-specific questions.
3. While the answer streams in, point out: this isn't Groq answering from
   its own training data — point at the "Sources (N)" section that appears
   and expand a citation card to show the actual retrieved judgment
   excerpt, case name, court, date, and relevance score.
4. Click "View full case" to show the case detail page came from the same
   Postgres-backed knowledge base.
5. Ask the deliberately unrelated question (GDPR) and show the fixed
   insufficient-evidence message instead of a fabricated answer — this is
   the strongest single proof that the system is grounded, not a generic
   chatbot.
6. Optionally show the search page filtering by court/date/act.

## 7. Common failure and recovery

- **Backend won't start, complains about a missing/insecure setting**:
  double check `backend/.env` has all the fields above; `APP_ENV=development`
  avoids the strict production checks.
- **Backend starts but `/health` hangs or times out on first request**:
  this is the embedding model loading (a few seconds to ~1 minute on a cold
  cache) — wait, don't restart.
- **"insufficient evidence" on a question that should match a seeded
  case**: rephrase closer to the case's actual terminology (see
  `DEMO_QUESTIONS.md`); this is the similarity-threshold gate working as
  designed, not a bug.
- **CORS error in the browser console**: confirm `CORS_ORIGINS` in
  `backend/.env` includes `http://localhost:5173` exactly, then restart the
  backend.
- **Database connection refused**: confirm you're using the Supabase
  Session Pooler host/port, not the Direct Connection ones (see
  `docs/deployment.md`).

## Outstanding before this is fully verified

This guide has **not yet been run end-to-end** in this environment — it's
waiting on two real values only you have: your actual Supabase Session
Pooler password, and your Groq API key. Once `backend/.env` has both, run
sections 2–3 above once and this becomes a fully verified, tested
procedure rather than a documented plan.
