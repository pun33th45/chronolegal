"""
Handles uploaded PDF/DOCX/TXT documents, extracts text, chunks, and embeds.
"""

import asyncio
import uuid

from loguru import logger

from app.core.redis import cache
from app.services.ai.chunker import TextChunker
from app.services.ai.embedding_service import EmbeddingService


class DocumentProcessor:
    async def process_upload(
        self,
        content: bytes,
        filename: str,
        content_type: str,
        user_id: str,
    ) -> str:
        task_id = str(uuid.uuid4())
        await cache.set(
            f"upload:{task_id}",
            {"status": "queued", "filename": filename},
            ttl=3600,
        )
        asyncio.create_task(
            self._process(task_id, content, filename, content_type, user_id)
        )
        return task_id

    async def get_task_status(self, task_id: str) -> dict:
        status = await cache.get(f"upload:{task_id}")
        if status is None:
            return {"status": "not_found"}
        return status

    async def _process(
        self,
        task_id: str,
        content: bytes,
        filename: str,
        content_type: str,
        user_id: str,
    ) -> None:
        try:
            await cache.set(f"upload:{task_id}", {"status": "extracting"}, ttl=3600)
            text = await self._extract_text(content, content_type, filename)

            await cache.set(f"upload:{task_id}", {"status": "chunking"}, ttl=3600)
            chunker = TextChunker()
            chunks = chunker.chunk(text)

            await cache.set(
                f"upload:{task_id}",
                {"status": "embedding", "chunks": len(chunks)},
                ttl=3600,
            )

            doc_id = f"upload_{user_id}_{task_id[:8]}"
            ids = [f"{doc_id}__chunk_{i}" for i in range(len(chunks))]
            metadatas = [
                {
                    "case_id": doc_id,
                    "case_name": filename,
                    "court": "Uploaded Document",
                    "date": "",
                    "chunk_index": i,
                }
                for i in range(len(chunks))
            ]

            embedder = EmbeddingService()
            await embedder.upsert_chunks(chunks, metadatas, ids)

            await cache.set(
                f"upload:{task_id}",
                {"status": "done", "doc_id": doc_id, "chunk_count": len(chunks)},
                ttl=3600,
            )
            logger.info(f"Document processed: task_id={task_id}, chunks={len(chunks)}")

        except Exception as e:
            logger.error(f"Document processing failed: task_id={task_id}, error={e}")
            await cache.set(
                f"upload:{task_id}", {"status": "failed", "error": str(e)}, ttl=3600
            )

    async def _extract_text(
        self, content: bytes, content_type: str, filename: str
    ) -> str:
        loop = asyncio.get_event_loop()

        if content_type == "application/pdf" or filename.endswith(".pdf"):
            return await loop.run_in_executor(None, self._extract_pdf, content)
        if content_type in (
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ) or filename.endswith((".doc", ".docx")):
            return await loop.run_in_executor(None, self._extract_docx, content)
        return content.decode("utf-8", errors="replace")

    def _extract_pdf(self, content: bytes) -> str:
        import io
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _extract_docx(self, content: bytes) -> str:
        import io
        from docx import Document

        doc = Document(io.BytesIO(content))
        return "\n".join(para.text for para in doc.paragraphs)
