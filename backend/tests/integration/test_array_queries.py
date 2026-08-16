"""Integration tests for the PostgreSQL ARRAY query paths.

These exercise the real ARRAY(Text) operators (ANY via .any(), unnest())
against a live PostgreSQL database (see tests/conftest.py). CaseService,
AnalyticsService, and LegalCase are used directly — nothing is mocked.
"""

from datetime import date

import pytest

from app.models.case import LegalCase
from app.services.legal.analytics_service import AnalyticsService
from app.services.legal.case_service import CaseService


def _case(case_id: str, **kwargs) -> LegalCase:
    kwargs.setdefault("case_name", f"Case {case_id}")
    return LegalCase(case_id=case_id, **kwargs)


@pytest.mark.asyncio
async def test_list_cases_filters_by_act(db):
    """LegalCase.acts.any(act) matches only cases containing that exact act."""
    db.add_all(
        [
            _case("act-filter-match", acts=["Indian Penal Code"]),
            _case("act-filter-other", acts=["Companies Act"]),
            _case("act-filter-null", acts=None),
        ]
    )
    await db.commit()

    svc = CaseService(db)
    results = await svc.list_cases(act="Indian Penal Code")

    assert {c.case_id for c in results} == {"act-filter-match"}


@pytest.mark.asyncio
async def test_get_distinct_acts_and_judges_unnest_and_dedupe(db):
    """func.unnest() flattens + dedupes + sorts across rows, excludes NULLs."""
    db.add_all(
        [
            _case("distinct-1", acts=["A", "B"], judges=["J1", "J2"]),
            _case("distinct-2", acts=["B", "C"], judges=["J2", "J3"]),
            _case("distinct-3", acts=None, judges=None),
        ]
    )
    await db.commit()

    svc = CaseService(db)
    assert await svc.get_distinct_acts() == ["A", "B", "C"]
    assert await svc.get_distinct_judges() == ["J1", "J2", "J3"]


@pytest.mark.asyncio
async def test_get_top_acts_judges_keywords_aggregate_counts(db):
    """Raw SQL unnest()+GROUP BY+COUNT aggregates correctly across rows,
    for all three columns that share this query shape."""
    common = {"acts": ["X"], "judges": ["J-Common"], "keywords": ["K-Common"]}
    rare = {"acts": ["Y"], "judges": ["J-Rare"], "keywords": ["K-Rare"]}
    db.add_all(
        [
            _case("agg-1", **common),
            _case("agg-2", **common),
            _case("agg-3", **common),
            _case("agg-4", **rare),
        ]
    )
    await db.commit()

    svc = AnalyticsService(db)

    top_acts = await svc.get_top_acts()
    assert [(i.name, i.count) for i in top_acts] == [("X", 3), ("Y", 1)]

    top_judges = await svc.get_top_judges()
    assert [(i.name, i.count) for i in top_judges] == [("J-Common", 3), ("J-Rare", 1)]

    top_keywords = await svc.get_top_keywords()
    assert [(i.name, i.count) for i in top_keywords] == [
        ("K-Common", 3),
        ("K-Rare", 1),
    ]


@pytest.mark.asyncio
async def test_array_null_and_empty_behavior(db):
    """NULL and empty ('{}') arrays never contribute to ANY()/unnest()
    results, and neither causes a query error."""
    db.add_all(
        [
            _case("edge-null", acts=None),
            _case("edge-empty", acts=[]),
            _case("edge-normal", acts=["Z"]),
        ]
    )
    await db.commit()

    case_svc = CaseService(db)

    results = await case_svc.list_cases(act="Z")
    assert {c.case_id for c in results} == {"edge-normal"}

    assert await case_svc.get_distinct_acts() == ["Z"]

    analytics_svc = AnalyticsService(db)
    top_acts = await analytics_svc.get_top_acts()
    assert [(i.name, i.count) for i in top_acts] == [("Z", 1)]


@pytest.mark.asyncio
async def test_get_case_trends_buckets_by_year_and_respects_cutoff(db):
    """get_case_trends' raw SQL uses EXTRACT(YEAR FROM judgment_date) and a
    NOW()-based year cutoff — both Postgres-specific and easy to get
    subtly wrong (off-by-one on the cutoff, NULL dates leaking into a
    bucket). This is the only test that actually exercises it against a
    real database rather than mocking the ORM call."""
    current_year = date.today().year
    db.add_all(
        [
            _case("trend-this-year-a", judgment_date=date(current_year, 1, 15)),
            _case("trend-this-year-b", judgment_date=date(current_year, 6, 1)),
            _case("trend-last-year", judgment_date=date(current_year - 1, 3, 1)),
            _case("trend-too-old", judgment_date=date(current_year - 5, 1, 1)),
            _case("trend-null-date", judgment_date=None),
        ]
    )
    await db.commit()

    svc = AnalyticsService(db)
    trends = await svc.get_case_trends(years=2)

    by_year = {t.year: t.count for t in trends}
    assert by_year.get(current_year) == 2
    assert by_year.get(current_year - 1) == 1
    assert (current_year - 5) not in by_year
