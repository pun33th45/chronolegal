"""Integration test for the real embedding -> Chroma vector-store round
trip. Unlike every other RAG-related test in this suite (test_rag_pipeline.py
mocks EmbeddingService/Reranker/generate_text entirely), this test makes NO
mocks on EmbeddingService, the Chroma client, vector upsert, or similarity
search — it exercises the actual chunk -> embed -> upsert -> retrieve path.

Query rewriting and LLM answer generation are a different stage of the RAG
pipeline (see rag_pipeline.py) and both call out to a real LLM provider
(rewrite_query -> generate_text) — deliberately out of scope here, since
this test is specifically about retrieval, not generation.

Model choice: EMBEDDING_MODEL is overridden to a small, standard,
publicly-available sentence-transformers model rather than the production
default (BAAI/bge-large-en-v1.5, ~1.3GB) — this is still the real
HuggingFaceEmbeddings code path via the project's existing
EMBEDDING_PROVIDER=huggingface config knob, just pointed at a CI-sized
real model instead of a fake/stubbed one. Requires network access to
huggingface.co to download the model on a cold cache (~1 minute the first
time; fast on any warm cache).

CHROMA_MODE is overridden to "embedded" (PersistentClient) pointed at a
fresh pytest tmp_path, so this test needs no external Chroma service and
cannot collide with any other test or real data.
"""

import pytest

from app.core.config import settings
from app.services.ai.chunker import TextChunker
from app.services.ai.embedding_service import (
    EmbeddingService,
    _get_chroma_client,
    _get_embedding_model,
)

_TEST_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@pytest.fixture(autouse=True)
def _clear_caches():
    _get_embedding_model.cache_clear()
    _get_chroma_client.cache_clear()
    yield
    _get_embedding_model.cache_clear()
    _get_chroma_client.cache_clear()


@pytest.mark.asyncio
async def test_real_embedding_and_chroma_retrieval_round_trip(tmp_path, monkeypatch):
    """Embeds two topically distinct legal-style chunks with a real
    embedding model, upserts them into a real embedded-Chroma collection,
    and verifies a query about one topic actually retrieves that topic's
    chunk over the unrelated one — proving real semantic retrieval, not
    merely that Chroma/the embedding model can be constructed."""
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "huggingface")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL", _TEST_EMBEDDING_MODEL)
    monkeypatch.setattr(settings, "CHROMA_MODE", "embedded")
    monkeypatch.setattr(settings, "CHROMA_PERSIST_DIRECTORY", str(tmp_path))

    chunker = TextChunker(chunk_size=300, chunk_overlap=0)

    fundamental_rights_text = (
        "The Supreme Court held that the right to life under Article 21 of "
        "the Constitution includes the right to live with human dignity, "
        "and that no person may be deprived of personal liberty except "
        "according to procedure established by law."
    )
    contract_law_text = (
        "The appellant argued that the agreement was void for lack of "
        "consideration under Section 25 of the Indian Contract Act, and "
        "that the respondent had failed to deliver the goods specified in "
        "the sale agreement."
    )

    rights_chunks = chunker.chunk(fundamental_rights_text)
    contract_chunks = chunker.chunk(contract_law_text)

    embedder = EmbeddingService()

    await embedder.upsert_chunks(
        chunks=rights_chunks,
        metadatas=[
            {
                "case_id": "test-rights-case",
                "case_name": "Test Rights Case",
                "chunk_index": i,
            }
            for i in range(len(rights_chunks))
        ],
        ids=[f"test-rights-case__chunk_{i}" for i in range(len(rights_chunks))],
    )
    await embedder.upsert_chunks(
        chunks=contract_chunks,
        metadatas=[
            {
                "case_id": "test-contract-case",
                "case_name": "Test Contract Case",
                "chunk_index": i,
            }
            for i in range(len(contract_chunks))
        ],
        ids=[f"test-contract-case__chunk_{i}" for i in range(len(contract_chunks))],
    )

    count = await embedder.get_collection_count()
    assert count == len(rights_chunks) + len(contract_chunks)

    results = await embedder.similarity_search(
        query="What did the court decide about the right to personal liberty?",
        n_results=1,
    )

    top_metadata = results["metadatas"][0][0]
    top_document = results["documents"][0][0].lower()

    assert top_metadata["case_id"] == "test-rights-case"
    assert "liberty" in top_document or "life" in top_document
