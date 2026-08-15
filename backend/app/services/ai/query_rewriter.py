"""
Query rewriter — expands and clarifies legal queries before retrieval.
"""

from app.core.redis import cache
from app.services.ai.llm_provider import generate_text

REWRITE_PROMPT = """You are a legal search query specialist. Your task is to rewrite the user's question into a precise legal search query that will retrieve the most relevant Indian legal judgments.

Rules:
- Expand abbreviations (e.g., IPC → Indian Penal Code)
- Add relevant legal terminology
- Keep the query concise (under 100 words)
- Preserve the original intent
- Output ONLY the rewritten query, nothing else

Original question: {query}

Rewritten query:"""


async def rewrite_query(query: str) -> str:
    cache_key = f"query_rewrite:{hash(query)}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    try:
        rewritten = await generate_text(REWRITE_PROMPT.format(query=query))
        rewritten = rewritten.strip()
        if rewritten and len(rewritten) < 500:
            await cache.set(cache_key, rewritten, ttl=3600)
            return rewritten
    except Exception:
        pass

    return query
