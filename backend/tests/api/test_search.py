"""Integration tests for the /search endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

MOCK_SEARCH_RESPONSE = {
    "query": "Article 21",
    "rewritten_query": "Article 21 right to life Indian Constitution",
    "results": [
        {
            "case_id": "maneka-gandhi-1978",
            "case_name": "Maneka Gandhi v. Union of India",
            "court": "Supreme Court of India",
            "judges": None,
            "judgment_date": "1978-01-25",
            "acts": ["Constitution of India"],
            "chunk_content": "Article 21 guarantees the right to life and personal liberty...",
            "similarity_score": 0.91,
            "rank": 1,
            "highlights": [],
            "chunk_id": "maneka-gandhi-1978__chunk_0",
            "page_number": None,
        }
    ],
    "total_results": 1,
    "search_type": "hybrid",
    "latency_ms": 120,
}


@pytest.fixture
def mock_search_service():
    from app.schemas.search import SearchResponse

    mock_result = SearchResponse(**MOCK_SEARCH_RESPONSE)
    with patch("app.api.v1.endpoints.search.SearchService") as MockSvc:
        instance = MockSvc.return_value
        instance.search = AsyncMock(return_value=mock_result)
        instance.get_suggestions = AsyncMock(
            return_value=["Maneka Gandhi", "Kesavananda Bharati"]
        )
        yield instance


@pytest.mark.asyncio
async def test_search_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/v1/search/", json={"query": "Article 21", "top_k": 5}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_search_returns_results(
    client: AsyncClient,
    auth_headers: dict,
    mock_search_service,
):
    with patch("app.services.legal.search_log_service.SearchLogService") as MockLog:
        MockLog.return_value.log = AsyncMock()
        resp = await client.post(
            "/api/v1/search/",
            json={"query": "Article 21", "top_k": 5, "search_type": "hybrid"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "total_results" in data
    assert data["query"] == "Article 21"


@pytest.mark.asyncio
async def test_search_suggestions(
    client: AsyncClient,
    auth_headers: dict,
    mock_search_service,
):
    resp = await client.get(
        "/api/v1/search/suggestions?q=Article&limit=5",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    suggestions = resp.json()
    assert isinstance(suggestions, list)


@pytest.mark.asyncio
async def test_search_filters_endpoint(
    client: AsyncClient,
    auth_headers: dict,
):
    with patch("app.services.legal.case_service.CaseService") as MockCaseSvc:
        instance = MockCaseSvc.return_value
        instance.get_distinct_courts = AsyncMock(
            return_value=["Supreme Court of India"]
        )
        instance.get_distinct_judges = AsyncMock(return_value=["Justice Chandrachud"])
        instance.get_distinct_acts = AsyncMock(return_value=["Constitution of India"])
        instance.get_distinct_decision_types = AsyncMock(return_value=["Allowed"])

        resp = await client.get("/api/v1/search/filters", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "courts" in data
    assert "acts" in data
