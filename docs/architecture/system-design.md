# ChronoLegal — System Design

## Overview

ChronoLegal is a **Retrieval-Augmented Generation (RAG)** platform specialising in Indian legal judgments. Users ask natural-language questions; the system retrieves relevant case law from a vector database, reranks results, and generates a grounded answer that cites real judgments.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                React 19 SPA (Vite + TailwindCSS)            │
│  Landing · Auth · Chat · Search · Analytics · Case Viewer   │
│  Zustand state · React Query cache · SSE streaming          │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS / WSS (Nginx reverse proxy)
┌──────────────────────────▼──────────────────────────────────┐
│                  FastAPI (Python 3.11)                       │
│  /auth · /chat · /search · /cases · /summary · /analytics   │
│  Pydantic v2 validation · JWT auth · rate limiting          │
└──┬─────────────┬─────────────┬──────────────────────────────┘
   │             │             │
┌──▼───┐   ┌────▼───┐   ┌─────▼───────────────────────────┐
│ PG16 │   │ Redis7 │   │         AI Pipeline              │
│(ORM) │   │(cache) │   │  Rewriter → Embedder → ChromaDB  │
└──────┘   └────────┘   │  → Reranker → LLM → SSE stream  │
                         └─────────────┬───────────────────┘
                                       │
                                ┌──────▼───────┐
                                │   Ollama     │
                                │ LLaMA 3.1 8B │
                                └──────────────┘
```

---

## Component Breakdown

### Frontend

| Component | Technology | Responsibility |
|-----------|-----------|----------------|
| Routing | React Router v6 | SPA navigation, protected routes |
| State | Zustand | Auth tokens, chat state |
| Server state | React Query | API caching, background refetch |
| Streaming | EventSource (SSE) | Token-by-token chat rendering |
| Charts | Recharts | Analytics visualisations |
| Animation | Framer Motion | Page transitions |
| UI primitives | Radix UI + CVA | Accessible headless components |

### Backend

| Layer | Technology | Responsibility |
|-------|-----------|----------------|
| Framework | FastAPI | Async HTTP, OpenAPI auto-docs |
| ORM | SQLAlchemy 2 (async) | PostgreSQL access |
| Validation | Pydantic v2 | Request/response schemas |
| Migrations | Alembic | Schema versioning |
| Auth | python-jose + passlib | JWT signing, bcrypt hashing |
| Cache | aioredis | Query result caching (5 min TTL) |
| Middleware | Custom | Rate limiting, security headers |

### AI Pipeline (RAG)

```
1. Query Rewriting    — LLM expands abbreviations, adds legal context
2. Embedding          — BAAI/bge-large-en-v1.5 (1024-dim, normalised)
3. Vector Search      — ChromaDB cosine similarity, top-50 candidates
4. Cross-Encoder Rerank — ms-marco-MiniLM-L-6-v2, reranks to top-5
5. Context Builder    — Concatenates chunk texts + metadata
6. LLM Generation     — LLaMA 3.1 8B via Ollama, anti-hallucination prompt
7. SSE Streaming      — Token-by-token delivery to client
```

---

## Data Flow: Chat Request

```
POST /api/v1/chat/stream
        │
        ▼
[Auth middleware] → validate JWT, load user
        │
        ▼
[Rate limiter]    → 30 req/min per user
        │
        ▼
[RAGPipeline.run()]
    ├── QueryRewriter.rewrite(question)          ~200ms
    ├── EmbeddingService.embed(rewritten_q)      ~80ms
    ├── ChromaDB.query(embedding, top_k=50)      ~30ms
    ├── Reranker.rerank(chunks, question)        ~150ms
    ├── PromptBuilder.build(top_k=5 chunks)      ~1ms
    └── LLMProvider.stream(prompt)               ~2-8s (token by token)
        │
        ▼
[SSE response]    → yield token events → citations event → done event
        │
        ▼
[ConversationService.save_message()]  → PostgreSQL
```

---

## Database Schema

```
users
  id (uuid PK) · email (unique) · password_hash · full_name · role · created_at

conversations
  id (uuid PK) · user_id (FK) · title · created_at · updated_at

messages
  id (uuid PK) · conversation_id (FK) · role (user/assistant) · content
  citations (jsonb) · created_at

legal_cases
  id (uuid PK) · case_name · citation (unique) · court · bench (jsonb)
  year · date_decided · judgment_text · acts_cited (jsonb)
  sections_cited (jsonb) · outcome · indexed_at

case_chunks
  id (uuid PK) · case_id (FK) · chunk_index · chunk_text
  embedding_id (chroma doc id) · metadata (jsonb)

search_feedback
  id · message_id (FK) · user_id (FK) · rating · comment · created_at

search_logs
  id · user_id (FK) · query · result_count · response_ms · created_at
```

---

## Caching Strategy

| Layer | TTL | Key |
|-------|-----|-----|
| Search results | 5 min | `search:{sha256(query+filters)}` |
| Case metadata | 1 hour | `case:{case_id}` |
| Analytics dashboard | 10 min | `analytics:dashboard:{user_id}` |
| Embedding vectors | Permanent | ChromaDB (content-addressed) |

---

## Scaling Considerations

| Bottleneck | Current | Production path |
|-----------|---------|-----------------|
| LLM inference | Ollama (local GPU) | vLLM cluster / OpenAI API |
| Embeddings | HuggingFace (in-process) | Dedicated inference service |
| ChromaDB | Single-node | Qdrant / Weaviate cluster |
| PostgreSQL | Docker single-node | RDS Multi-AZ |
| API | Single FastAPI worker | Multiple Uvicorn workers behind Nginx |

---

## Security

- JWT HS256 with configurable expiry
- Passwords bcrypt-hashed (12 rounds)
- Rate limiting (Nginx + FastAPI middleware)
- CORS restricted to configured origins
- Security headers: `X-Content-Type-Options`, `X-Frame-Options`, `HSTS`
- No raw SQL — all queries via SQLAlchemy ORM
- Input validation on all endpoints via Pydantic

---

## Deployment

```
Nginx (SSL termination, gzip, rate zones)
  ├── /            → Frontend SPA (static files)
  ├── /api/        → FastAPI backend (upstream)
  └── /ws/         → WebSocket upgrade

Docker Compose services:
  backend · frontend · postgres · chroma · redis · ollama · nginx
```

CI/CD via GitHub Actions:
- **CI** (`ci.yml`): lint → test → build on every push
- **CD** (`cd.yml`): push GHCR images → SSH deploy on main branch
