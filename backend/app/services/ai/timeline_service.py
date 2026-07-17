from pydantic import BaseModel, model_validator

from loguru import logger

from app.schemas.case import TimelineEvent
from app.services.ai.json_parser import parse_llm_json
from app.services.ai.llm_provider import generate_text
from app.services.ai.prompt_templates import TIMELINE_EXTRACTION


class _TimelineList(BaseModel):
    """Wraps a bare JSON array so parse_llm_json can validate it uniformly."""
    events: list[TimelineEvent] = []

    @model_validator(mode="before")
    @classmethod
    def _coerce_array(cls, data: object) -> object:
        if isinstance(data, list):
            return {"events": data}
        return data


class TimelineService:
    async def generate(self, case: any) -> list[TimelineEvent]:
        text = case.full_text or case.summary or ""
        if not text.strip():
            return []

        text_excerpt = text[:10000]
        prompt = TIMELINE_EXTRACTION.format(text=text_excerpt)

        try:
            raw = await generate_text(prompt)
            parsed = await parse_llm_json(raw, _TimelineList, generate_fn=generate_text)
            events = [e for e in parsed.events if e.date and e.event]
            events.sort(key=lambda e: e.date)
            return events
        except Exception as e:
            logger.error(f"Timeline generation failed: {e}")
            return []
