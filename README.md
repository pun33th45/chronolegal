# ChronoLegal — AI-Powered Legal Research Platform

> Final Year Major Project | Legal Question Answering and Case Analytics using ChronoLegal and Large Language Models

---

## Overview

ChronoLegal is a **production-grade AI Legal Research Platform** that enables lawyers, judges, students, and researchers to search, analyze, and understand Indian legal judgments using cutting-edge AI.

### Key Capabilities

| Feature | Details |
|---------|---------|
| **Legal QA** | Ask natural language questions, get grounded answers with citations |
| **Semantic Search** | Search by meaning using BAAI/bge-large-en-v1.5 embeddings |
| **Zero Hallucination** | Every answer grounded in retrieved documents — never fabricates |
| **Case Summary** | Concise, detailed, or bullet-point AI summaries |
| **NER Extraction** | Judges, courts, acts, sections, lawyers, organizations |
| **Timeline** | Auto-generated chronological event timelines from judgments |
| **Analytics** | Charts: top acts, courts, trends, decision types, keywords |
| **Citation Explorer** | Every answer shows ranked citations with similarity scores |
| **Conversation Memory** | Full ChatGPT-like multi-conversation history |
| **Streaming** | Real-time streaming responses via SSE |
| **Admin Dashboard** | Dataset stats, embedding progress, search logs |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      React Frontend (Vite)                   │
│  Landing │ Auth │ Chat │ Search │ Analytics │ Case Viewer   │
└────────────────────┬────────────────────────────────────────┘
                     │ REST API + SSE streaming
┌────────────────────▼────────────────────────────────────────┐
│                    FastAPI Backend                           │
│  Auth │ Chat │ Search │ Cases │ Summary │ NER │ Analytics   │
└──────┬────────┬──────────┬───────────────────────────────── ┘
       │        │          │
  ┌────▼──┐ ┌──▼────┐ ┌───▼───────────────────────────────┐
  │Postgres│ │ Redis │ │           AI Pipeline              │
  │  (ORM) │ │(Cache)│ │  Query Rewriter → Embedder →       │
  └────────┘ └───────┘ │  ChromaDB → Reranker → LLM        │
                        └────────┬───────────────────────────┘
                                 │
                          ┌──────▼──────┐
                          │   Ollama    │
                          │ LLaMA 3.1   │
                          └─────────────┘
```

## RAG Pipeline

```
User Question
     ↓
Query Rewriter (LLM)
     ↓
Embedding Generator (BAAI/bge-large-en-v1.5)
     ↓
Semantic Search (ChromaDB — cosine similarity)
     ↓
Cross-Encoder Reranker (ms-marco-MiniLM-L-6-v2)
     ↓
Top-K Documents + Context Builder
     ↓
Prompt Engineering (anti-hallucination system prompt)
     ↓
LLM Generation (LLaMA 3.1 8B / Qwen3 / Mistral)
     ↓
Grounded Answer + Citation Cards
```

---

## Tech Stack

**Frontend**: React 19 · TypeScript · Vite · TailwindCSS · Framer Motion · React Query · Recharts · React Markdown · Lucide Icons · Zustand

**Backend**: Python 3.11 · FastAPI · SQLAlchemy (async) · Alembic · Pydantic v2

**AI/ML**: LangChain · BAAI/bge-large-en-v1.5 · cross-encoder/ms-marco-MiniLM-L-6-v2 · LLaMA 3.1 8B (Ollama)

**Databases**: PostgreSQL 16 · ChromaDB (vector) · Redis 7 (cache)

**Infrastructure**: Docker · Docker Compose · Nginx

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- 16GB RAM minimum (for LLM)
- 50GB disk space

### 1. Clone and configure
```bash
git clone <repo>
cd chronolegal
cp .env.example .env
# Edit .env — especially SECRET_KEY and JWT_SECRET_KEY
```

### 2. Start services
```bash
make dev
# OR: docker compose up --build -d
```

### 3. Pull the LLM model
```bash
docker compose exec ollama ollama pull llama3.1:8b
# Alternative: qwen3, mistral
```

### 4. Create admin user
```bash
docker compose exec backend python scripts/setup/create_admin.py
```

### 5. Load the dataset (choose one option)
```bash
# Option A: Download ChronoLegal from HuggingFace
docker compose exec backend python scripts/data/01_download_dataset.py
docker compose exec backend python scripts/data/02_preprocess.py
docker compose exec backend python scripts/data/03_ingest_to_db.py
docker compose exec backend python scripts/data/04_generate_embeddings.py

# Option B: One command
make data-pipeline
```

### 6. Access
| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/api/docs |
| ChromaDB | http://localhost:8001 |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Register user |
| POST | `/api/v1/auth/login` | Login |
| POST | `/api/v1/chat/` | Chat (non-streaming) |
| POST | `/api/v1/chat/stream` | Chat (SSE streaming) |
| GET | `/api/v1/chat/conversations` | List conversations |
| POST | `/api/v1/search/` | Semantic search |
| GET | `/api/v1/cases/{case_id}` | Get case |
| POST | `/api/v1/summary/` | Generate summary |
| POST | `/api/v1/ner/` | Extract entities |
| GET | `/api/v1/timeline/{case_id}` | Get timeline |
| GET | `/api/v1/analytics/dashboard` | Analytics |
| GET | `/api/v1/admin/stats` | Admin stats |

---

## Project Structure

```
chronolegal/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/    # REST endpoints
│   │   ├── core/                # Config, DB, security
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── services/
│   │   │   ├── ai/              # RAG, embeddings, LLM, NER, summary
│   │   │   └── legal/           # Business logic
│   │   └── middleware/          # Rate limiting, security
│   └── tests/
├── frontend/
│   └── src/
│       ├── pages/               # All page components
│       ├── components/          # Reusable UI
│       ├── services/            # API client
│       ├── store/               # Zustand state
│       └── types/               # TypeScript types
├── ai/                          # Standalone AI scripts
├── scripts/
│   ├── data/                    # Dataset pipeline
│   └── setup/                   # Admin creation, model pull
├── database/migrations/         # SQL migrations
├── nginx/                       # Nginx config + Dockerfile
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

## Changing the LLM

Edit `.env`:
```bash
LLM_PROVIDER=ollama    # or openai / anthropic
LLM_MODEL=llama3.1:8b # or qwen3, mistral, gpt-4o-mini
```

No code changes needed — the provider factory handles it.

---

## Running Tests

```bash
# Backend
docker compose exec backend pytest --cov=app

# Or locally
cd backend && pip install -r requirements-dev.txt
pytest
```

---

## License

MIT © 2025 ChronoLegal
