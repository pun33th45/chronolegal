"""Tests for utility functions."""
import pytest
from app.utils.text import clean_legal_text, extract_section_numbers, extract_citations, word_count
from app.utils.validators import is_safe_query, sanitize_search_query, is_valid_case_id
from app.utils.pagination import Page


# ── text utils ──────────────────────────────────────────────────────────────

def test_clean_legal_text_removes_control_chars():
    raw = "Legal\x00text\x01with\x02control chars"
    cleaned = clean_legal_text(raw)
    assert "\x00" not in cleaned
    assert "Legal" in cleaned


def test_clean_legal_text_normalizes_unicode():
    raw = "café Ａ"  # accented + fullwidth
    cleaned = clean_legal_text(raw)
    assert cleaned  # Should not crash


def test_extract_section_numbers():
    text = "Under Section 302 and Section 420 of IPC, and Article 21 of the Constitution."
    sections = extract_section_numbers(text)
    assert "Section 302" in sections or "302" in str(sections)


def test_extract_citations():
    text = "As held in (2018) 4 SCC 123 and AIR 1978 SC 597."
    citations = extract_citations(text)
    assert len(citations) >= 1


def test_word_count():
    assert word_count("one two three") == 3
    assert word_count("") == 0


# ── validator utils ──────────────────────────────────────────────────────────

def test_is_safe_query_blocks_xss():
    assert not is_safe_query("<script>alert(1)</script>")


def test_is_safe_query_blocks_sqli():
    assert not is_safe_query("' OR 1=1 --")


def test_is_safe_query_allows_legal_query():
    assert is_safe_query("What are the fundamental rights under Article 14?")


def test_sanitize_removes_html():
    dirty = "<b>Article 21</b> <script>bad()</script>"
    clean = sanitize_search_query(dirty)
    assert "<" not in clean
    assert "Article 21" in clean


def test_is_valid_case_id():
    assert is_valid_case_id("CIVIL-APPEAL-2023-001")
    assert is_valid_case_id("kesavananda-bharati-1973")
    assert not is_valid_case_id("case with spaces!")
    assert not is_valid_case_id("")


# ── pagination ───────────────────────────────────────────────────────────────

def test_page_dataclass():
    items = [1, 2, 3]
    page = Page(items=items, total=15, page=1, page_size=3)
    assert page.total_pages == 5
    assert page.has_next is True
    assert page.has_prev is False


def test_page_last_page():
    page = Page(items=[1], total=5, page=2, page_size=3)
    assert page.has_next is False
    assert page.has_prev is True
    assert page.total_pages == 2
