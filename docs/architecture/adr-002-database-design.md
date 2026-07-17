# ADR-002: Database Design — Dual-Store Architecture

**Status**: Accepted  
**Date**: 2025-01-01  
**Author**: ChronoLegal Team

---

## Context

Legal case data requires two very different query patterns:

1. **Structured queries** — "cases from Supreme Court between 2000–2010 citing Article 21"
2. **Semantic queries** — "cases about right to privacy and surveillance"

No single database handles both optimally.

---

## Decision

Use a **dual-store architecture**:

- **PostgreSQL 16** — structured data, user data, full case metadata
- **ChromaDB** — vector embeddings for semantic search

The two stores are linked by `case_id` (UUID), enabling hybrid search: retrieve candidates from ChromaDB by semantic similarity, then enrich with full metadata from PostgreSQL.

---

## Schema Decisions

### Why UUIDs instead of serial integers?
- Cases are ingested from HuggingFace in parallel — no coordination needed for ID generation
- Safer to expose in API responses (no enumeration attacks)
- Easy future migration to distributed PostgreSQL

### Why JSONB for `acts_cited`, `sections_cited`, `bench`?
- These are variable-length arrays with no fixed schema
- JSONB allows GIN indexing for containment queries: `acts_cited @> '["Constitution of India"]'`
- Avoids a separate many-to-many join table for read-heavy workloads

### Why a separate `case_chunks` table?
- Each judgment is split into ~300-token chunks for embedding
- Chunks store their `embedding_id` (ChromaDB document ID) for bidirectional lookup
- Allows re-embedding a single case without touching other cases

### Why store `citations` as JSONB in `messages`?
- Citations are a read-only snapshot of what the RAG retrieved at query time
- They don't need to be queried independently — fetched as part of the message
- JSONB avoids a `message_citations` junction table

---

## Query Patterns

### Hybrid search (most common)
```sql
-- 1. ChromaDB returns case_ids ordered by embedding similarity
-- 2. PostgreSQL enriches with metadata
SELECT c.* FROM legal_cases c
WHERE c.id = ANY(:case_ids)
ORDER BY array_position(:case_ids, c.id);
```

### Faceted filtering
```sql
SELECT * FROM legal_cases
WHERE court = 'Supreme Court of India'
  AND year BETWEEN 2000 AND 2023
  AND acts_cited @> '["Constitution of India"]'::jsonb
LIMIT 20;
```

### Analytics aggregation
```sql
SELECT year, count(*) FROM legal_cases GROUP BY year ORDER BY year;
SELECT unnest(acts_cited) AS act, count(*) FROM legal_cases GROUP BY act ORDER BY count DESC LIMIT 10;
```

---

## Consequences

**Positive**:
- PostgreSQL handles auth, conversations, analytics with ACID guarantees
- ChromaDB handles high-dimensional similarity search natively
- `case_id` as foreign key keeps stores in sync
- GIN indexes on JSONB columns make faceted search fast

**Negative**:
- Two stores to backup and manage
- Sync can drift if `DocumentProcessor` fails mid-ingest (mitigated: re-index is idempotent)
- ChromaDB does not support joins — PostgreSQL must enrich results
