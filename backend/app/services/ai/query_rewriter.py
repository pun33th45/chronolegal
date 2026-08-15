"""
Query rewriter — expands and clarifies legal queries before retrieval.
"""

from app.core.redis import cache
from app.services.ai.llm_provider import generate_text

REWRITE_PROMPT = (
    "You are a legal search query specialist. Your task is to rewrite the "
    "user's question into a precise legal search query that will retrieve "
    "the most relevant Indian legal judgments.\n"
    "\n"
    "Rules:\n"
    "- Expand abbreviations (e.g., IPC → Indian Penal Code)\n"
    "- Add relevant legal terminology\n"
    "- Keep the query concise (under 100 words)\n"
    "- Preserve the original intent\n"
    "- Output ONLY the rewritten query, nothing else\n"
    "\n"
    "Original question: {query}\n"
    "\n"
    "Rewritten query:"
)


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
