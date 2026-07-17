"""Unit tests for parse_llm_json."""
import pytest
from pydantic import BaseModel

from backend.app.services.ai.json_parser import parse_llm_json


class _Simple(BaseModel):
    name: str = ""
    value: int = 0


class _ListWrapper(BaseModel):
    items: list[str] = []

    from pydantic import model_validator

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data):
        if isinstance(data, list):
            return {"items": data}
        return data


@pytest.mark.asyncio
async def test_direct_parse():
    result = await parse_llm_json('{"name": "foo", "value": 42}', _Simple)
    assert result.name == "foo"
    assert result.value == 42


@pytest.mark.asyncio
async def test_fenced_json():
    raw = '```json\n{"name": "bar", "value": 1}\n```'
    result = await parse_llm_json(raw, _Simple)
    assert result.name == "bar"


@pytest.mark.asyncio
async def test_fenced_no_lang():
    raw = '```\n{"name": "baz"}\n```'
    result = await parse_llm_json(raw, _Simple)
    assert result.name == "baz"


@pytest.mark.asyncio
async def test_trailing_text_extraction():
    raw = 'Here is your JSON:\n{"name": "extracted", "value": 7}\nDone.'
    result = await parse_llm_json(raw, _Simple)
    assert result.name == "extracted"
    assert result.value == 7


@pytest.mark.asyncio
async def test_malformed_no_retry_returns_defaults():
    raw = "This is not JSON at all."
    result = await parse_llm_json(raw, _Simple)
    assert result.name == ""
    assert result.value == 0


@pytest.mark.asyncio
async def test_retry_with_generate_fn():
    async def mock_llm(prompt: str) -> str:
        return '{"name": "fixed", "value": 99}'

    raw = "BROKEN{name: fixed, value: 99}"
    result = await parse_llm_json(raw, _Simple, generate_fn=mock_llm)
    assert result.name == "fixed"
    assert result.value == 99


@pytest.mark.asyncio
async def test_array_coercion_via_model_validator():
    raw = '["alpha", "beta"]'
    result = await parse_llm_json(raw, _ListWrapper)
    assert result.items == ["alpha", "beta"]
