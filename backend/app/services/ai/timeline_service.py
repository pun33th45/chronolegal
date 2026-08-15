"""
Timeline extraction via map-reduce:
  Map  — extract events from each ~8 k-char chunk in parallel
  Merge — combine all event lists
  Dedupe — drop near-duplicate (date, event) pairs using token overlap
  Sort  — chronological order by date string

The old truncate-to-10k approach missed events in long judgments.
"""

import asyncio
import re
from pydantic import BaseModel, model_validator

from loguru import logger

from app.schemas.case import TimelineEvent
from app.services.ai.json_parser import parse_llm_json
from app.services.ai.llm_provider import generate_text
from app.services.ai.prompt_templates import TIMELINE_EXTRACTION

_CHUNK_CHARS = 8_000
_OVERLAP_CHARS = 500


class _TimelineList(BaseModel):
    """Wraps a bare JSON array so parse_llm_json can validate it uniformly."""

    events: list[TimelineEvent] = []

    @model_validator(mode="before")
    @classmethod
    def _coerce_array(cls, data: object) -> object:
        if isinstance(data, list):
            return {"events": data}
        return data


def _tokenize(text: str) -> set[str]:
    return set(re.sub(r"[^\w\s]", "", text.lower()).split())


def _is_duplicate(
    event_a: TimelineEvent, event_b: TimelineEvent, threshold: float = 0.7
) -> bool:
    """True if two events have the same date and highly overlapping event descriptions."""
    if event_a.date.strip() != event_b.date.strip():
        return False
    a_tok = _tokenize(event_a.event)
    b_tok = _tokenize(event_b.event)
    if not a_tok or not b_tok:
        return False
    overlap = len(a_tok & b_tok) / max(len(a_tok), len(b_tok))
    return overlap >= threshold


def _dedupe(events: list[TimelineEvent]) -> list[TimelineEvent]:
    unique: list[TimelineEvent] = []
    for candidate in events:
        if not any(_is_duplicate(candidate, kept) for kept in unique):
            unique.append(candidate)
    return unique


async def _extract_chunk(chunk: str) -> list[TimelineEvent]:
    """Run TIMELINE_EXTRACTION LLM call on one chunk."""
    prompt = TIMELINE_EXTRACTION.format(text=chunk)
    try:
        raw = await generate_text(prompt)
        parsed = await parse_llm_json(raw, _TimelineList, generate_fn=generate_text)
        return [e for e in parsed.events if e.date and e.event]
    except Exception as exc:
        logger.warning(f"Timeline chunk extraction failed: {exc}")
        return []


class TimelineService:
    async def generate(self, case: any) -> list[TimelineEvent]:
        text = case.full_text or case.summary or ""
        if not text.strip():
            return []

        # Split text into overlapping chunks
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + _CHUNK_CHARS
            chunks.append(text[start:end])
            start = (
                end - _OVERLAP_CHARS
            )  # overlap to avoid missing cross-boundary events
            if start <= 0:
                break

        # Map: extract events from each chunk concurrently
        chunk_results = await asyncio.gather(*[_extract_chunk(c) for c in chunks])

        # Merge
        all_events: list[TimelineEvent] = []
        for result in chunk_results:
            all_events.extend(result)

        if not all_events:
            return []

        # Dedupe + sort
        unique_events = _dedupe(all_events)
        unique_events.sort(key=lambda e: e.date)
        return unique_events
