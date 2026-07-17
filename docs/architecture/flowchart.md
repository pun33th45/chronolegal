# ChronoLegal — Flowcharts

---

## 1. RAG Pipeline — Detailed Flowchart

```mermaid
flowchart TD
    A([User submits question]) --> B[JWT Authentication]
    B --> C{Token valid?}
    C -- No --> D([Return 401])
    C -- Yes --> E[Rate Limit Check]
    E --> F{Within limit?}
    F -- No --> G([Return 429])
    F -- Yes --> H[Query Rewriter]

    H --> I[Send to LLM:\nExpand abbreviations\nAdd legal terminology\nClarify ambiguities]
    I --> J[Rewritten Query]

    J --> K[Embedding Generator\nBAAI/bge-large-en-v1.5]
    K --> L[1024-dim Query Vector]

    L --> M[ChromaDB Cosine Search\ntop_k = 50]
    M --> N{Apply metadata filters?\ncourt / year / acts}
    N -- Yes --> O[Filtered candidate set]
    N -- No --> P[Full candidate set]
    O --> Q[Cross-Encoder Reranker\nms-marco-MiniLM-L-6-v2]
    P --> Q

    Q --> R[Top 5 Chunks\nreranked by relevance]

    R --> S{Sufficient context?}
    S -- No --> T([Return: 'Insufficient evidence\nin legal corpus'])
    S -- Yes --> U[Context Builder\nConcatenate chunks + metadata]

    U --> V[Prompt Engineering\nAnti-hallucination system prompt\nInject context + question]

    V --> W[LLM Generation\nLLaMA 3.1 8B / OpenAI / Anthropic]
    W --> X[SSE Token Stream]
    X --> Y[Append citations\ncase_name + citation + score]
    Y --> Z[Save to PostgreSQL\nconversation + message + citations]
    Z --> AA([Stream complete → Client])
```

---

## 2. Data Ingestion Pipeline

```mermaid
flowchart TD
    A([Start: run data pipeline]) --> B[01_download_dataset.py\nFetch ChronoLegal from HuggingFace]
    B --> C{Download success?}
    C -- No --> D([Error: Check internet / HF token])
    C -- Yes --> E[02_preprocess.py\nClean HTML/whitespace\nNormalize dates\nExtract metadata]

    E --> F[03_ingest_to_db.py\nINSERT into legal_cases\nSkip duplicates by citation]
    F --> G{DB insert OK?}
    G -- No --> H([Error: Check PostgreSQL connection])
    G -- Yes --> I[04_generate_embeddings.py\nFetch un-indexed cases]

    I --> J{Cases remaining?}
    J -- No --> K([Complete — all cases embedded])
    J -- Yes --> L[Load next case]

    L --> M[RecursiveChunker\nchunk_size=300 tokens\noverlap=50 tokens]
    M --> N[Batch chunks × 32]
    N --> O[EmbeddingService\nBAAI/bge-large-en-v1.5\nembed batch]
    O --> P[ChromaDB\nadd_documents\nwith metadata]
    P --> Q[PostgreSQL\nINSERT case_chunks\nUPDATE indexed_at]
    Q --> J
```

---

## 3. Authentication Flow

```mermaid
flowchart TD
    A([HTTP Request]) --> B[Extract Authorization header]
    B --> C{Header present?}
    C -- No --> D([401 Not authenticated])
    C -- Yes --> E[Decode JWT\nHS256 + SECRET_KEY]
    E --> F{Signature valid?}
    F -- No --> G([401 Could not validate credentials])
    F -- Yes --> H{Token expired?}
    H -- Yes --> I([401 Token expired])
    H -- No --> J[Extract user_id from sub claim]
    J --> K[Load user from PostgreSQL]
    K --> L{User exists and active?}
    L -- No --> M([401 User not found])
    L -- Yes --> N{Admin route?}
    N -- Yes --> O{Role = admin?}
    O -- No --> P([403 Not enough permissions])
    O -- Yes --> Q([Proceed to endpoint])
    N -- No --> Q
```

---

## 4. Search Decision Flow

```mermaid
flowchart TD
    A([POST /search/]) --> B[Validate request schema]
    B --> C{Redis cache hit?}
    C -- Yes --> D([Return cached results\nX-Cache: HIT])
    C -- No --> E[Embed query\nbge-large-en-v1.5]

    E --> F{Filters specified?}
    F -- Yes --> G[ChromaDB query\nwith where clause\ncourt / year / acts]
    F -- No --> H[ChromaDB query\nno filters\ntop_k = 50]

    G --> I[Merge results]
    H --> I

    I --> J[Fetch case metadata\nfrom PostgreSQL]
    J --> K[Deduplicate by case_id\nkeep highest chunk score]
    K --> L[Paginate results]
    L --> M[Store in Redis\nTTL = 300 seconds]
    M --> N[Log to search_logs]
    N --> O([Return paginated results])
```

---

## 5. Frontend Routing Flow

```mermaid
flowchart TD
    A([Browser navigates to URL]) --> B{JWT in localStorage?}
    B -- No --> C{Is public route?\n/ /login /register}
    C -- Yes --> D([Render public page])
    C -- No --> E([Redirect to /login])

    B -- Yes --> F[AuthProvider\nvalidate token via GET /auth/me]
    F --> G{Token valid?}
    G -- No --> H[Clear localStorage]
    H --> E

    G -- Yes --> I{Route?}
    I -- /dashboard --> J([DashboardPage])
    I -- /chat/:id? --> K([ChatPage])
    I -- /search --> L([SearchPage])
    I -- /analytics --> M([AnalyticsPage])
    I -- /cases/:id --> N([CaseViewerPage])
    I -- /admin --> O{user.role = admin?}
    O -- No --> P([Redirect /dashboard])
    O -- Yes --> Q([AdminPage])
    I -- /profile --> R([ProfilePage])
    I -- /settings --> S([SettingsPage])
```
