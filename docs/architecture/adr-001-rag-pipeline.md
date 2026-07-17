# ADR-001: RAG Pipeline Architecture

**Status**: Accepted  
**Date**: 2025-01-01  
**Author**: ChronoLegal Team

---

## Context

ChronoLegal needs to answer legal questions grounded in real case law. Two main approaches were evaluated:

1. **Fine-tuned LLM** — train a model on Indian legal judgments
2. **RAG (Retrieval-Augmented Generation)** — retrieve relevant chunks at query time and pass them to a general-purpose LLM

---

## Decision

We chose **RAG** with a multi-stage pipeline:

```
Query Rewriting → Embedding → ChromaDB → Cross-Encoder Reranking → LLM
```

### Rationale

| Concern | Fine-tuning | RAG (chosen) |
|---------|-------------|--------------|
| Hallucination | High — model bakes in "facts" | Low — grounded in retrieved text |
| Knowledge freshness | Requires re-training | Add new cases without retraining |
| Citation accuracy | Cannot reliably cite | Returns exact chunk + case metadata |
| Training cost | High (GPU hours, data prep) | Zero |
| Inference speed | Fast (no retrieval) | ~500ms extra for retrieval |
| Explainability | Black-box | Fully traceable to source chunks |

For a **legal** domain, citation accuracy and zero hallucination outweigh speed advantages of fine-tuning.

---

## Pipeline Stages

### 1. Query Rewriting
**Tool**: LLM (same provider as generation)  
**Why**: Raw user questions ("what happened in kesavananda?") miss legal terminology. The rewriter expands abbreviations, adds full case names, and injects legal context to improve retrieval precision.

### 2. Embedding
**Model**: `BAAI/bge-large-en-v1.5` (1024 dimensions)  
**Why**: Top performer on BEIR benchmark for legal/long-document retrieval. Better than `all-MiniLM` for domain-specific text. Runs locally via HuggingFace — no external API needed.

### 3. Vector Search
**Store**: ChromaDB with cosine similarity  
**Why**: ChromaDB offers a simple HTTP API, supports metadata filtering (year, court, acts), and runs well in Docker. Top-50 candidates retrieved to give the reranker sufficient signal.

### 4. Cross-Encoder Reranking
**Model**: `cross-encoder/ms-marco-MiniLM-L-6-v2`  
**Why**: Bi-encoder (embedding) retrieval is fast but imprecise — it scores query and document independently. Cross-encoders score the pair jointly, dramatically improving top-5 precision at ~150ms cost (acceptable).

### 5. LLM Generation
**Default**: LLaMA 3.1 8B via Ollama  
**Why**: Runs fully locally — no API costs, no data leaves the machine. The factory pattern (`LLMProvider`) allows swapping to OpenAI/Anthropic without code changes.

### 6. Anti-Hallucination Prompt
System prompt instructs the model to:
- Only state facts present in the provided context
- Always cite the source case
- Say "I cannot find information on this" if context is insufficient

---

## Consequences

**Positive**:
- Every answer traceable to a real judgment
- New cases indexed in minutes (no retraining)
- LLM provider hot-swappable
- Retrieval quality improvable by swapping models independently

**Negative**:
- ~500ms extra latency for retrieval (mitigated by SSE streaming — user sees tokens immediately)
- ChromaDB must be kept in sync with PostgreSQL (handled by `DocumentProcessor`)
- Reranker adds ~150ms per query (cross-encoder is CPU-bound)
