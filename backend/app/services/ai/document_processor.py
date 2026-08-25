"""
Handles uploaded PDF/DOCX/TXT documents, extracts text, chunks, and embeds.
"""

import asyncio
import re
import uuid

from dateutil import parser as date_parser
from loguru import logger

from app.services.ai.chunker import LegalChunker
from app.services.ai.embedding_service import EmbeddingService
from app.services.ai.ner_service import NERService

# The event loop only holds a *weak* reference to tasks created via
# asyncio.create_task — an unreferenced task can be garbage-collected
# mid-execution, silently abandoning upload processing. Keeping a strong
# reference here (and discarding it once done) prevents that.
_background_tasks: set[asyncio.Task] = set()

# Upload task status is tracked in-process rather than via the Redis-backed
# `cache` used elsewhere: every other use of `cache` treats a miss as "not
# cached, recompute" (a real but harmless degradation when Redis is down —
# e.g. this app's default REDIS_URL points at the `redis` Docker Compose
# hostname, which doesn't resolve when running bare uvicorn locally). Upload
# status has no such fallback — it *is* the data, not a cache of it — so a
# Redis outage would otherwise make every "processing your document" poll
# return 404 forever. A single local uvicorn process is exactly this app's
# deployment model, so a plain dict is a correct store here, not a shortcut.
_upload_status: dict[str, dict] = {}


class DocumentProcessor:
    async def process_upload(
        self,
        content: bytes,
        filename: str,
        content_type: str,
        user_id: str,
    ) -> str:
        task_id = str(uuid.uuid4())
        _upload_status[task_id] = {
            "status": "queued",
            "filename": filename,
            "user_id": user_id,
        }
        task = asyncio.create_task(
            self._process(task_id, content, filename, content_type, user_id)
        )
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        return task_id

    async def get_task_status(self, task_id: str, user_id: str) -> dict | None:
        """Returns None if the task doesn't exist or belongs to another user."""
        status = _upload_status.get(task_id)
        if status is None or status.get("user_id") != user_id:
            return None
        return status

    async def _process(
        self,
        task_id: str,
        content: bytes,
        filename: str,
        content_type: str,
        user_id: str,
    ) -> None:
        # Every status update below must carry user_id/filename forward —
        # each write replaces the whole stored value, so omitting them
        # would silently break get_task_status's ownership check the
        # moment processing moves past "queued".
        base = {"user_id": user_id, "filename": filename}
        try:
            _upload_status[task_id] = {**base, "status": "extracting"}
            text = await self._extract_text(content, content_type, filename)
            if not text.strip():
                raise ValueError("No extractable text found in document")

            doc_id = f"upload_{user_id}_{task_id[:8]}"
            case_name = self._detect_case_title(text) or filename.rsplit(".", 1)[0]

            _upload_status[task_id] = {**base, "status": "chunking"}
            chunker = LegalChunker()
            chunks = chunker.chunk_legal(
                text, {"case_id": doc_id, "case_name": case_name}
            )

            _upload_status[task_id] = {
                **base,
                "status": "extracting_entities",
                "chunks": len(chunks),
            }
            ner_service = NERService()
            entities = await ner_service.extract(text)
            if not any(
                [
                    entities.judges,
                    entities.courts,
                    entities.acts,
                    entities.sections,
                    entities.parties,
                ]
            ):
                # A single fully-empty result is more likely a transient LLM
                # hiccup (rate limit, truncated JSON) than a genuinely
                # entity-free judgment — retry once before accepting it.
                entities = await ner_service.extract(text)
            court = entities.courts[0] if entities.courts else "Uploaded Document"
            raw_date = entities.dates[0] if entities.dates else None
            judgment_date = None
            if raw_date:
                try:
                    judgment_date = date_parser.parse(raw_date, fuzzy=True).date()
                except (ValueError, OverflowError):
                    judgment_date = None
            for _, meta in chunks:
                meta["court"] = court
                meta["date"] = raw_date or ""

            _upload_status[task_id] = {
                **base,
                "status": "embedding",
                "chunks": len(chunks),
            }

            ids = [f"{doc_id}__chunk_{i}" for i in range(len(chunks))]
            texts = [c[0] for c in chunks]
            metadatas = [
                {k: v for k, v in meta.items() if v is not None} for _, meta in chunks
            ]

            embedder = EmbeddingService()
            embeddings = await embedder.embed_texts(texts)

            _upload_status[task_id] = {
                **base,
                "status": "indexing",
                "chunks": len(chunks),
            }
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: embedder.collection.upsert(
                    documents=texts,
                    embeddings=embeddings,  # type: ignore[arg-type]
                    metadatas=metadatas,  # type: ignore[arg-type]
                    ids=ids,
                ),
            )

            from app.core.database import AsyncSessionLocal
            from app.services.legal.case_service import CaseService

            async with AsyncSessionLocal() as db:
                case_svc = CaseService(db)
                case = await case_svc.create_case(
                    case_id=doc_id,
                    case_name=case_name,
                    full_text=text,
                    court=court,
                    source_file=filename,
                )
                case.judges = entities.judges or None
                case.acts = entities.acts or None
                case.sections = entities.sections or None
                case.parties = entities.parties or None
                case.judgment_date = judgment_date
                case.date_raw = raw_date
                case.is_embedded = True
                case.chunk_count = len(chunks)
                await case_svc.add_chunks(case.id, chunks, ids)
                await db.commit()

            _upload_status[task_id] = {
                **base,
                "status": "done",
                "doc_id": doc_id,
                "case_id": doc_id,
                "chunk_count": len(chunks),
            }
            logger.info(f"Document processed: task_id={task_id}, chunks={len(chunks)}")

        except Exception as e:
            logger.error(f"Document processing failed: task_id={task_id}, error={e}")
            _upload_status[task_id] = {**base, "status": "failed", "error": str(e)}

    _CASE_TITLE_RE = re.compile(
        r"^.{1,150}?\b(?:v\.?|vs\.?|versus)\b.{1,150}$", re.IGNORECASE
    )

    @classmethod
    def _detect_case_title(cls, text: str) -> str | None:
        """Indian judgments conventionally open with the case title in
        "X v. Y" / "X vs. Y" / "X versus Y" form (every seeded demo case
        follows this same convention) — checking the first few non-empty
        lines for that pattern gives a real case name instead of falling
        back to the uploaded filename, which is what the query rewriter
        and Case Viewer otherwise display verbatim."""
        for line in text.strip().splitlines()[:5]:
            line = line.strip()
            if line and cls._CASE_TITLE_RE.match(line):
                return line
        return None

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
