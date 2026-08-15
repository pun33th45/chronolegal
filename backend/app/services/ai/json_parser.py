"""
Robust LLM JSON parser with three-stage fallback:
  1. Direct json.loads after stripping markdown fences
  2. Regex-extract the first JSON object/array from the raw text
  3. One LLM retry asking the model to fix its own malformed output

Validates the result against a Pydantic schema before returning.
"""

import json
import re
from typing import Any, Awaitable, Callable, TypeVar

from loguru import logger
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# Greedy regex that finds the outermost {...} or [...] block.
# Handles one level of nesting — sufficient for the flat schemas used here.
_JSON_BLOCK_RE = re.compile(
    r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}|\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\])",
    re.DOTALL,
)


def _strip_fences(text: str) -> str:
    """Remove ```json … ``` or ``` … ``` markdown fences."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    # Drop opening fence line (```json or ```)
    start = 1
    if len(lines) > 1 and lines[1].strip().lower() in ("json", ""):
        start = 2
    # Drop closing fence
    end = len(lines)
    for i in range(len(lines) - 1, 0, -1):
        if lines[i].strip() == "```":
            end = i
            break
    return "\n".join(lines[start:end]).strip()


def _load(raw: str) -> Any:
    return json.loads(raw)


def _to_schema(data: Any, schema: type[T]) -> T:
    if isinstance(data, dict):
        return schema(**data)
    return schema.model_validate(data)


async def parse_llm_json(
    raw: str,
    schema: type[T],
    generate_fn: Callable[[str], Awaitable[str]] | None = None,
) -> T:
    """
    Parse *raw* LLM output into *schema*, with three-stage fallback.

    Args:
        raw:         Raw string returned by the LLM.
        schema:      Pydantic model class to validate against.
        generate_fn: Optional async callable(prompt) -> str used for the retry.
                     Pass ``generate_text`` from llm_provider.

    Returns:
        A validated instance of *schema*.  Falls back to ``schema()`` (empty
        defaults) only if all three stages fail.
    """
    # Stage 1 — strip fences, direct parse
    cleaned = _strip_fences(raw)
    try:
        return _to_schema(_load(cleaned), schema)
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Stage 2 — regex-extract first JSON block from original text
    match = _JSON_BLOCK_RE.search(raw)
    if match:
        try:
            return _to_schema(_load(match.group(0)), schema)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    # Stage 3 — ask the LLM to self-correct
    if generate_fn is not None:
        fix_prompt = (
            "The following text contains malformed JSON. "
            "Return ONLY the corrected JSON with no other text:\n\n"
            f"{raw}\n\nFixed JSON:"
        )
        try:
            fixed_raw = await generate_fn(fix_prompt)
            fixed_cleaned = _strip_fences(fixed_raw)
            fixed_match = _JSON_BLOCK_RE.search(fixed_raw)
            candidate = (
                fixed_cleaned
                if fixed_cleaned
                else (fixed_match.group(0) if fixed_match else "")
            )
            if candidate:
                return _to_schema(_load(candidate), schema)
        except Exception as exc:
            logger.warning(f"parse_llm_json retry failed ({schema.__name__}): {exc}")

    logger.warning(
        f"parse_llm_json: all stages failed for {schema.__name__}, returning defaults"
    )
    return schema()
