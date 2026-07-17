"""
Recursive text chunker with overlap — optimized for legal documents.
"""
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings


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
                char_offset = end  # advance past this chunk; backing off by CHUNK_OVERLAP caused wrong offsets for repeated text
        return result
