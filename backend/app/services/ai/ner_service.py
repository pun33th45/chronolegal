import json

from loguru import logger

from app.schemas.case import LegalEntityExtraction
from app.services.ai.llm_provider import generate_text
from app.services.ai.prompt_templates import NER_EXTRACTION


class NERService:
    async def extract(self, text: str) -> LegalEntityExtraction:
        text_excerpt = text[:8000]
        prompt = NER_EXTRACTION.format(text=text_excerpt)

        try:
            raw = await generate_text(prompt)
            # Strip markdown code blocks if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip().rstrip("```").strip()

            data = json.loads(raw)
            return LegalEntityExtraction(**data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"NER JSON parse failed: {e}. Returning empty extraction.")
            return LegalEntityExtraction()
        except Exception as e:
            logger.error(f"NER extraction failed: {e}")
            return LegalEntityExtraction()
