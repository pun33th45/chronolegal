"""
Chunkers for legal documents.

TextChunker   — generic recursive character splitter (unchanged behaviour).
LegalChunker  — legal-structure-aware: splits on numbered paragraphs / section
                headers first, falls back to recursive splitting.  Stores the
                nearest section header in chunk metadata so citations can say
                "para 14" or "HELD".
"""

import re

from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger

from app.core.config import settings

# ---------------------------------------------------------------------------
# Patterns that signal a new section in an Indian judgment
# ---------------------------------------------------------------------------
_SECTION_RE = re.compile(
    r"^(\d+)\.\s"  # "14. The court held…"
    r"|^(para(?:graph)?\s*\d+[\.:)])"  # "Para 14:" / "Paragraph 3."
    r"|^((?:JUDGMENT|ORDER|FACTS?|ISSUE|HELD|ANALYSIS"
    r"|REASONING|CONCLUSION|BACKGROUND|SUBMISSIONS?"
    r"|ARGUMENTS?|FINDING|RELIEF|DECREE)\b.*)",
    re.IGNORECASE | re.MULTILINE,
)


def _split_by_legal_structure(text: str) -> list[tuple[str, str | None]]:
    """
    Split *text* at legal section boundaries.

    Returns a list of (section_text, header_label) pairs where header_label is
    the matched heading (e.g. "14." or "HELD") or None for the preamble.
    """
    sections: list[tuple[str, str | None]] = []
    last_end = 0
    last_header: str | None = None

    for m in _SECTION_RE.finditer(text):
        chunk = text[last_end : m.start()].strip()
        if chunk:
            sections.append((chunk, last_header))
        # Pick the first non-None group as the header label
        last_header = next((g for g in m.groups() if g is not None), None)
        last_end = m.start()

    tail = text[last_end:].strip()
    if tail:
        sections.append((tail, last_header))

    return sections


# ---------------------------------------------------------------------------
# Generic chunker
# ---------------------------------------------------------------------------


class TextChunker:
    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size or settings.CHUNK_SIZE,
            chunk_overlap=chunk_overlap or settings.CHUNK_OVERLAP,
            length_function=len,
            separators=["\n\n", "\n", ". ", "? ", "! ", " ", ""],
            keep_separator=True,
        )

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []
        return self._splitter.split_text(text)

    def chunk_with_metadata(
        self, text: str, base_metadata: dict
    ) -> list[tuple[str, dict]]:
        chunks = self.chunk(text)
        result = []
        char_offset = 0
        for i, chunk in enumerate(chunks):
            start = text.find(chunk, char_offset)
            end = start + len(chunk) if start != -1 else -1
            meta = {
                **base_metadata,
                "chunk_index": i,
                "start_char": start,
                "end_char": end,
            }
            result.append((chunk, meta))
            if start != -1:
                char_offset = end  # advance past this chunk; backing off caused wrong offsets for repeated text
        return result


# ---------------------------------------------------------------------------
# Legal-structure-aware chunker
# ---------------------------------------------------------------------------


class LegalChunker(TextChunker):
    """
    Splits on numbered paragraphs / section headers first, then recursively
    splits any section that still exceeds chunk_size.  The nearest section
    header is stored in ``meta["section_header"]`` so that citations can
    surface "para 14" instead of a bare character offset.
    """

    _MIN_SECTIONS = 3  # fall back to recursive if too few sections found

    def chunk_legal(self, text: str, base_metadata: dict) -> list[tuple[str, dict]]:
        sections = _split_by_legal_structure(text)

        if len(sections) < self._MIN_SECTIONS:
            logger.debug(
                "LegalChunker: too few sections, falling back to recursive splitting"
            )
            return self.chunk_with_metadata(text, base_metadata)

        result: list[tuple[str, dict]] = []
        char_offset = 0
        chunk_index = 0

        for section_text, header in sections:
            # If the section fits in one chunk, keep it whole
            if len(section_text) <= (settings.CHUNK_SIZE * 2):
                sub_chunks = [section_text]
            else:
                sub_chunks = self._splitter.split_text(section_text)

            for sub in sub_chunks:
                start = text.find(sub, char_offset)
                end = start + len(sub) if start != -1 else -1
                meta = {
                    **base_metadata,
                    "chunk_index": chunk_index,
                    "start_char": start,
                    "end_char": end,
                    "section_header": header,
                }
                result.append((sub, meta))
                if start != -1:
                    char_offset = end
                chunk_index += 1

        return result
