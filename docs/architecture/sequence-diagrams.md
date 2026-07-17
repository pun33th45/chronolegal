# ChronoLegal — Sequence Diagrams

---

## 1. User Registration & Login

```mermaid
sequenceDiagram
    actor User
    participant FE as React Frontend
    participant API as FastAPI Backend
    participant DB as PostgreSQL

    User->>FE: Fill register form (name, email, password)
    FE->>API: POST /api/v1/auth/register
    API->>API: Validate Pydantic schema
    API->>API: bcrypt.hash(password, rounds=12)
    API->>DB: INSERT INTO users ...
    DB-->>API: user row
    API->>API: create_access_token(user_id, role)
    API-->>FE: 201 { access_token, user }
    FE->>FE: Store token in Zustand + localStorage
    FE-->>User: Redirect → /dashboard

    Note over User,DB: Subsequent Login

    User->>FE: Fill login form
    FE->>API: POST /api/v1/auth/login
    API->>DB: SELECT user WHERE email=?
    DB-->>API: user row
    API->>API: bcrypt.verify(password, hash)
    alt Credentials valid
        API->>API: create_access_token(user_id)
        API-->>FE: 200 { access_token }
        FE-->>User: Redirect → /dashboard
    else Invalid
        API-->>FE: 401 Incorrect email or password
        FE-->>User: Show error toast
    end
```

---

## 2. RAG Chat — Streaming Q&A

```mermaid
sequenceDiagram
    actor User
    participant FE as React Frontend
    participant API as FastAPI + RAGPipeline
    participant QR as QueryRewriter
    participant EM as EmbeddingService
    participant VDB as ChromaDB
    participant RR as Reranker
    participant LLM as Ollama / LLM
    participant DB as PostgreSQL

    User->>FE: Type question + press Enter
    FE->>API: POST /api/v1/chat/stream (SSE)
    API->>API: Verify JWT token
    API->>API: Check rate limit (30 req/min)

    API->>QR: rewrite(question)
    QR->>LLM: "Expand and clarify: {question}"
    LLM-->>QR: rewritten_query
    QR-->>API: rewritten_query

    API->>EM: embed(rewritten_query)
    EM-->>API: query_vector [1024-dim]

    API->>VDB: query(vector, top_k=50, filters)
    VDB-->>API: 50 candidate chunks + scores

    API->>RR: rerank(chunks, question)
    RR-->>API: top 5 chunks (cross-encoder scores)

    API->>API: build_context(top_5_chunks)
    API->>API: build_prompt(context, question)

    loop Token streaming
        API->>LLM: stream_generate(prompt)
        LLM-->>API: token
        API-->>FE: SSE event: {type:"token", data:"..."}
        FE->>FE: Append token to UI
    end

    API-->>FE: SSE event: {type:"citations", data:[...]}
    FE->>FE: Render citation cards

    API-->>FE: SSE event: {type:"done", data:{conversation_id, message_id}}

    API->>DB: INSERT INTO messages (user msg + assistant msg + citations)
    DB-->>API: OK

    FE-->>User: Complete answer with citation cards
```

---

## 3. Semantic Search

```mermaid
sequenceDiagram
    actor User
    participant FE as React Frontend
    participant API as FastAPI
    participant Cache as Redis
    participant EM as EmbeddingService
    participant VDB as ChromaDB
    participant DB as PostgreSQL

    User->>FE: Type search query + apply filters
    FE->>API: POST /api/v1/search/ {query, filters, page}
    API->>API: Verify JWT

    API->>Cache: GET search:{hash(query+filters+page)}
    alt Cache hit (TTL 5 min)
        Cache-->>API: cached results
        API-->>FE: 200 results (X-Cache: HIT)
    else Cache miss
        API->>EM: embed(query)
        EM-->>API: query_vector

        API->>VDB: query(vector, top_k=50, where={court, year_range, acts})
        VDB-->>API: matching chunks with scores

        API->>DB: SELECT * FROM legal_cases WHERE id IN (...)
        DB-->>API: full case metadata

        API->>API: merge_and_deduplicate(chunks, cases)
        API->>API: paginate(results, page, page_size)

        API->>Cache: SET search:{hash} = results (TTL 300s)
        API-->>FE: 200 {results, total, page, query_time_ms}
    end

    API->>DB: INSERT INTO search_logs (query, filters, result_count, response_ms)

    FE-->>User: Search result cards with similarity scores
```

---

## 4. Case Summary Generation

```mermaid
sequenceDiagram
    actor User
    participant FE as React Frontend
    participant API as FastAPI
    participant Cache as Redis
    participant SS as SummaryService
    participant LLM as Ollama / LLM
    participant DB as PostgreSQL

    User->>FE: Open Case Viewer → click "Generate Summary"
    FE->>API: POST /api/v1/summary/ {case_id, style:"concise"}
    API->>API: Verify JWT

    API->>Cache: GET summary:{case_id}:{style}
    alt Cache hit (TTL 1 hr)
        Cache-->>API: cached summary
        API-->>FE: 200 {summary}
    else Cache miss
        API->>DB: SELECT judgment_text FROM legal_cases WHERE id=?
        DB-->>API: judgment_text

        API->>SS: summarize(judgment_text, case_meta, style)
        SS->>SS: Truncate text to 8000 tokens if needed
        SS->>LLM: generate(summary_prompt)
        LLM-->>SS: summary text
        SS-->>API: {summary, word_count}

        API->>Cache: SET summary:{case_id}:{style} (TTL 3600s)
        API-->>FE: 200 {case_id, summary, style, word_count}
    end

    FE-->>User: Rendered summary with copy button
```

---

## 5. Document Ingestion Pipeline

```mermaid
sequenceDiagram
    participant Script as scripts/data/
    participant HF as HuggingFace Hub
    participant DP as DocumentProcessor
    participant Chunker as RecursiveChunker
    participant EM as EmbeddingService
    participant VDB as ChromaDB
    participant DB as PostgreSQL

    Script->>HF: download ChronoLegal dataset
    HF-->>Script: raw JSON records

    Script->>Script: 02_preprocess.py (clean, normalize)
    Script->>DB: 03_ingest_to_db.py — INSERT INTO legal_cases

    Script->>DB: fetch all cases without embeddings
    DB-->>Script: case rows

    loop For each case
        Script->>DP: process(case)
        DP->>Chunker: chunk(judgment_text, size=300, overlap=50)
        Chunker-->>DP: [chunk_1, chunk_2, ..., chunk_N]

        loop For each chunk batch (32 at a time)
            DP->>EM: embed_batch(chunks)
            EM-->>DP: embeddings [N × 1024]
            DP->>VDB: add_documents(chunks, embeddings, metadata)
            VDB-->>DP: embedding_ids
            DP->>DB: INSERT INTO case_chunks (chunk_index, embedding_id)
        end

        DP->>DB: UPDATE legal_cases SET indexed_at=now(), chunk_count=N
    end

    Script-->>Script: Pipeline complete — all cases embedded
```

---

## 6. NER Extraction

```mermaid
sequenceDiagram
    actor User
    participant FE as React Frontend
    participant API as FastAPI
    participant NER as NERService
    participant LLM as Ollama / LLM
    participant Cache as Redis

    User->>FE: Open Case Viewer → Entities tab
    FE->>API: POST /api/v1/ner/ {case_id}
    API->>API: Verify JWT

    API->>Cache: GET ner:{case_id}
    alt Cache hit
        Cache-->>API: entities JSON
    else Cache miss
        API->>NER: extract(judgment_text)
        NER->>NER: Chunk text into 4000-token windows
        loop For each window
            NER->>LLM: extract_entities(window, ner_prompt)
            LLM-->>NER: {judges, advocates, courts, acts, sections, ...}
        end
        NER->>NER: merge_and_deduplicate(all_windows)
        NER-->>API: entities
        API->>Cache: SET ner:{case_id} (TTL 1hr)
    end

    API-->>FE: 200 entities
    FE-->>User: Entity tabs with highlighted names
```
