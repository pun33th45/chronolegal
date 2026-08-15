from datetime import datetime, timezone

from app.schemas.case import SummaryResponse
from app.services.ai.llm_provider import generate_text
from app.services.ai.prompt_templates import (
    SUMMARY_BULLET,
    SUMMARY_CONCISE,
    SUMMARY_DETAILED,
)


class SummaryService:
    _TEMPLATES = {
        "concise": SUMMARY_CONCISE,
        "detailed": SUMMARY_DETAILED,
        "bullet": SUMMARY_BULLET,
    }

    async def generate(
        self, case: any, summary_type: str, max_length: int
    ) -> SummaryResponse:
        text = case.full_text or case.headnotes or case.summary or ""
        if not text.strip():
            return SummaryResponse(
                case_id=case.case_id,
                case_name=case.case_name,
                summary_type=summary_type,
                summary="No text available for summarization.",
                generated_at=datetime.now(timezone.utc),
            )

        # Truncate to avoid context overflow (~12k chars ≈ 3k tokens)
        text_excerpt = text[:12000]
        template = self._TEMPLATES.get(summary_type, SUMMARY_CONCISE)
        prompt = template.format(text=text_excerpt, max_length=max_length)

        summary = await generate_text(prompt)

        return SummaryResponse(
            case_id=case.case_id,
            case_name=case.case_name,
            summary_type=summary_type,
            summary=summary.strip(),
            generated_at=datetime.now(timezone.utc),
        )
