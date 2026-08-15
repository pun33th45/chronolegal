"""
Robust date parsing for Indian legal documents.
Handles many real-world date formats found in judgments.
"""

from datetime import date
from typing import Optional

from dateutil import parser as dateutil_parser


_FORMATS = [
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%B %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
    "%b %d, %Y",
    "%Y",
    "%B %Y",
    "%b %Y",
]


def parse_date(raw: str) -> Optional[date]:
    """Try multiple formats then fall back to dateutil."""
    if not raw or not raw.strip():
        return None

    raw = raw.strip()

    # Fast path: already ISO
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass

    import datetime

    for fmt in _FORMATS:
        try:
            return datetime.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue

    # Slow path: dateutil (handles "3rd January 2020", etc.)
    try:
        return dateutil_parser.parse(raw, dayfirst=True).date()
    except Exception:
        return None


def format_date_for_display(d: Optional[date]) -> str:
    if d is None:
        return "Date unknown"
    return d.strftime("%-d %B %Y") if hasattr(d, "strftime") else str(d)
