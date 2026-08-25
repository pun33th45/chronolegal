"""
Query rewriter — expands and clarifies legal queries before retrieval.
"""

import hashlib
import re

from app.core.redis import cache
from app.services.ai.llm_provider import generate_text

REWRITE_PROMPT = (
    "You are a legal search query specialist. Your task is to rewrite the "
    "user's question into a precise legal search query that will retrieve "
    "the most relevant passages from Indian legal judgments.\n"
    "\n"
    "Rules:\n"
    "- Expand abbreviations (e.g., IPC → Indian Penal Code)\n"
    "- Add relevant legal terminology\n"
    "- Preserve every entity, case reference, Article, Act, section, date, "
    "and name already present in the question — never drop or generalize them\n"
    "- Keep the query concise (under 100 words)\n"
    "- Preserve the original intent\n"
    '- If the question refers to "this case", "this judgment", "here", '
    "or similar, and no specific case name is given below or in the "
    'question itself, keep that same generic reference (e.g. "this case") '
    "in your rewrite — do NOT invent, guess, or insert a case name\n"
    "- NEVER output a placeholder such as [case name], [Case Name], [X], "
    "___, or similar bracketed/blank filler for information you don't "
    "actually have — if you don't know it, omit it instead\n"
    "- Output ONLY the rewritten query, nothing else\n"
    "{case_context}"
    "\n"
    "Original question: {query}\n"
    "\n"
    "Rewritten query:"
)

# Catches leftover template filler the rewriter LLM occasionally invents
# when a question refers to "this case" without naming it (e.g. "[case
# name]", "[Case Name]", "[X]") — a real, observed failure mode, not a
# hypothetical one: such a rewrite embeds as near-meaningless text and
# collapses retrieval scores for an otherwise perfectly valid question.
_PLACEHOLDER_RE = re.compile(r"\[[^\]]{1,40}\]|\b___+\b")


async def rewrite_query(query: str, case_name: str | None = None) -> str:
    # hashlib (stable across processes) instead of the builtin hash()
    # (per-process-randomized by PYTHONHASHSEED since Python 3.3) — with
    # unstable keys, a cache entry written by one worker is never found by
    # another, silently defeating this cache under any multi-worker deploy.
    cache_key = (
        "query_rewrite:"
        + hashlib.md5(f"{case_name or ''}\x00{query}".encode()).hexdigest()
    )
    cached = await cache.get(cache_key)
    if cached:
        return cached

    case_context = (
        f'\nThe question is about this specific case: "{case_name}". '
        'Use this exact name if the question refers to "this case" or '
        "similar — never invent a different one.\n"
        if case_name
        else ""
    )

    try:
        rewritten = await generate_text(
            REWRITE_PROMPT.format(query=query, case_context=case_context)
        )
        rewritten = rewritten.strip()
        if rewritten and len(rewritten) < 500 and not _PLACEHOLDER_RE.search(rewritten):
            await cache.set(cache_key, rewritten, ttl=3600)
            return rewritten
    except Exception:
        pass

    return query
