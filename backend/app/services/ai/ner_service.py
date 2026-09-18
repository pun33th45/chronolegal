from loguru import logger

from app.schemas.case import LegalEntityExtraction
from app.services.ai.json_parser import parse_llm_json
from app.services.ai.llm_provider import generate_text
from app.services.ai.prompt_templates import NER_EXTRACTION


class NERService:
    async def extract(self, text: str) -> LegalEntityExtraction:
        text_excerpt = text[:8000]
        prompt = NER_EXTRACTION.format(text=text_excerpt)

        try:
            raw = await generate_text(prompt)
            if not raw.strip():
                # The reasoning model occasionally spends its whole budget on
                # internal reasoning and emits no final content. Retrying the
                # same generation (not asking it to "fix" empty JSON, which
                # parse_llm_json's stage 3 would otherwise do) resolves this
                # in practice — confirmed empirically: a second independent
                # call succeeds after a first empty one.
                logger.warning("NER generation returned empty content, retrying once")
                raw = await generate_text(prompt)
            return await parse_llm_json(
                raw, LegalEntityExtraction, generate_fn=generate_text
            )
        except Exception as e:
            logger.error(f"NER extraction failed: {e}")
            return LegalEntityExtraction()
