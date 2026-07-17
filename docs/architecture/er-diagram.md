# ChronoLegal — Entity Relationship Diagram

## Mermaid ER Diagram

```mermaid
erDiagram
    USERS {
        uuid        id PK
        varchar     email UK
        varchar     password_hash
        varchar     full_name
        varchar     role
        boolean     is_active
        timestamp   created_at
        timestamp   updated_at
    }

    CONVERSATIONS {
        uuid        id PK
        uuid        user_id FK
        varchar     title
        timestamp   created_at
        timestamp   updated_at
    }

    MESSAGES {
        uuid        id PK
        uuid        conversation_id FK
        varchar     role
        text        content
        jsonb       citations
        integer     token_count
        timestamp   created_at
    }

    LEGAL_CASES {
        uuid        id PK
        varchar     case_name
        varchar     citation UK
        varchar     court
        jsonb       bench
        integer     year
        date        date_decided
        text        judgment_text
        jsonb       acts_cited
        jsonb       sections_cited
        jsonb       keywords
        varchar     outcome
        integer     chunk_count
        timestamp   indexed_at
        timestamp   created_at
    }

    CASE_CHUNKS {
        uuid        id PK
        uuid        case_id FK
        integer     chunk_index
        text        chunk_text
        varchar     embedding_id
        jsonb       metadata
        timestamp   created_at
    }

    SEARCH_FEEDBACK {
        uuid        id PK
        uuid        message_id FK
        uuid        user_id FK
        integer     rating
        text        comment
        timestamp   created_at
    }

    SEARCH_LOGS {
        uuid        id PK
        uuid        user_id FK
        text        query
        jsonb       filters
        integer     result_count
        integer     response_ms
        timestamp   created_at
    }

    USERS ||--o{ CONVERSATIONS : "owns"
    USERS ||--o{ SEARCH_FEEDBACK : "submits"
    USERS ||--o{ SEARCH_LOGS : "generates"
    CONVERSATIONS ||--o{ MESSAGES : "contains"
    MESSAGES ||--o{ SEARCH_FEEDBACK : "receives"
    LEGAL_CASES ||--o{ CASE_CHUNKS : "split into"
```

---

## Table Descriptions

### `users`
Application users. `role` is either `user` or `admin`. Passwords stored as bcrypt hash (12 rounds).

### `conversations`
A named chat session belonging to a user. `title` is auto-generated from the first question (first 60 chars).

### `messages`
Individual turns in a conversation. `role` is `user` or `assistant`. `citations` is a JSONB array of `{case_name, citation, court, year, relevance_score, chunk_text}` objects attached to assistant messages.

### `legal_cases`
One row per Indian judgment. `bench`, `acts_cited`, `sections_cited`, and `keywords` use JSONB arrays. `citation` is unique (e.g. `(1973) 4 SCC 225`). GIN index on `acts_cited` enables containment queries.

### `case_chunks`
Each judgment is split into ~300-token overlapping chunks. `embedding_id` is the ChromaDB document ID, enabling bidirectional lookup between the relational store and the vector store.

### `search_feedback`
User thumbs-up/thumbs-down + optional comment on an assistant message. `rating` is 1–5.

### `search_logs`
Every search and chat query is logged for analytics and monitoring.

---

## Relationships Summary

| Relationship | Cardinality | Notes |
|-------------|------------|-------|
| user → conversations | 1:N | A user owns many conversations |
| conversation → messages | 1:N | Ordered by `created_at` |
| message → search_feedback | 1:1 | One feedback per message max |
| user → search_logs | 1:N | Every query logged |
| legal_case → case_chunks | 1:N | Chunks are the unit of embedding |

---

## ChromaDB (Vector Store)

Not a relational table — documents stored in ChromaDB with metadata:

```json
{
  "id": "<embedding_id>",
  "document": "<chunk_text>",
  "metadata": {
    "case_id": "<uuid>",
    "case_name": "Kesavananda Bharati v. State of Kerala",
    "citation": "(1973) 4 SCC 225",
    "court": "Supreme Court of India",
    "year": 1973,
    "chunk_index": 3,
    "acts_cited": ["Constitution of India"],
    "outcome": "Dismissed"
  }
}
```

Linked back to PostgreSQL via `case_id`.
