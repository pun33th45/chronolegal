"""
Text processing utilities for legal documents.
"""
import re
import unicodedata


def clean_legal_text(text: str) -> str:
    """Normalize whitespace, remove control chars, fix encoding artifacts."""
    if not text:
        return ""
    # Normalize unicode (e.g., smart quotes → ASCII)
    text = unicodedata.normalize("NFKC", text)
    # Remove control characters except newlines and tabs
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    # Normalize whitespace: collapse multiple spaces but preserve paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_section_numbers(text: str) -> list[str]:
    """Extract legal section references like 'Section 302 IPC', 'Art. 21', etc."""
    patterns = [
        r"[Ss]ection\s+\d+[A-Z]?\s*(?:of\s+the\s+[\w\s]+)?",
        r"[Aa]rt(?:icle)?\.?\s+\d+(?:\(\d+\))?",
        r"[Cc]l(?:ause)?\.?\s+\d+",
        r"[Rr]ule\s+\d+",
        r"[Oo]rder\s+[IVXLCDM]+",
    ]
    found = []
    for pat in patterns:
        found.extend(re.findall(pat, text))
    return list(dict.fromkeys(s.strip() for s in found))  # deduplicate, preserve order


def extract_citations(text: str) -> list[str]:
    """Extract case citations like '(2023) 1 SCC 123' or 'AIR 2019 SC 456'."""
    patterns = [
        r"\(\d{4}\)\s+\d+\s+[A-Z]+\s+\d+",
        r"AIR\s+\d{4}\s+[A-Z]+\s+\d+",
        r"\d{4}\s+\(\d+\)\s+[A-Z]+\s+\d+",
        r"[A-Z]+\s+\d+/\d{4}",
    ]
    found = []
    for pat in patterns:
        found.extend(re.findall(pat, text))
    return list(dict.fromkeys(s.strip() for s in found))


def truncate_text(text: str, max_chars: int, suffix: str = "…") -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(suffix)].rstrip() + suffix


def highlight_query_terms(text: str, query: str, tag: str = "**") -> str:
    """Wrap query terms with markdown bold markers for display."""
    terms = [t.strip() for t in query.split() if len(t.strip()) > 2]
    for term in terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        text = pattern.sub(lambda m: f"{tag}{m.group()}{tag}", text)
    return text


def word_count(text: str) -> int:
    return len(text.split()) if text else 0


def sentence_tokenize(text: str) -> list[str]:
    """Simple sentence splitter adequate for legal text."""
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    return [s.strip() for s in sentences if s.strip()]
