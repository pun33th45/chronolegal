import json

from loguru import logger

from app.schemas.case import TimelineEvent
from app.services.ai.llm_provider import generate_text
from app.services.ai.prompt_templates import TIMELINE_EXTRACTION


class TimelineService:
    async def generate(self, case: any) -> list[TimelineEvent]:
        text = case.full_text or case.summary or ""
        if not text.strip():
            return []

        text_excerpt = text[:10000]
        prompt = TIMELINE_EXTRACTION.format(text=text_excerpt)

        try:
            raw = await generate_text(prompt)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip().rstrip("```").strip()

            events_data = json.loads(raw)
            if not isinstance(events_data, list):
                return []

            events = []
            for item in events_data:
                if isinstance(item, dict) and item.get("date") and item.get("event"):
                    events.append(TimelineEvent(**item))

            events.sort(key=lambda e: e.date)
            return events

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Timeline JSON parse failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Timeline generation failed: {e}")
            return []
