"""
Input validators for legal queries and user inputs.
"""
import re


_BLOCKED_PATTERNS = [
    r"<script[^>]*>",
    r"javascript:",
    r"on\w+\s*=",            # onclick=, onload=, etc.
    r";\s*DROP\s+TABLE",
    r"UNION\s+SELECT",
    r"1\s*=\s*1\s*--",
]
_BLOCKED_RE = re.compile("|".join(_BLOCKED_PATTERNS), re.IGNORECASE)


def is_safe_query(text: str) -> bool:
    """Return False if the query contains XSS/SQLi/injection patterns."""
    return not bool(_BLOCKED_RE.search(text))


def sanitize_search_query(query: str) -> str:
    """Strip HTML, leading/trailing whitespace, limit length."""
    query = re.sub(r"<[^>]+>", "", query)   # strip HTML tags
    query = query.strip()
    return query[:1000]


def is_valid_case_id(case_id: str) -> bool:
    """Case IDs are alphanumeric with hyphens/underscores."""
    return bool(re.match(r"^[\w\-]{1,255}$", case_id))


def clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))
