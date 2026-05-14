from __future__ import annotations

import html
import re


_LINE_ENDING_RE = re.compile(r"\r\n?|\u2028|\u2029")
_HORIZONTAL_SPACE_RE = re.compile(r"[ \t\f\v]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_LINE_SPACE_RE = re.compile(r" *\n *")
# Common mojibake separators observed in some HWP direct-text extracts.
_MOJIBAKE_SEPARATOR_RE = re.compile(r"(?:[ྠĀ]\s*){2,}")


def normalize_extracted_text(text: str) -> str:
    """Normalize extracted text before saving or passing it to the RAG pipeline."""
    if not text:
        return ""

    normalized = html.unescape(text)
    normalized = _MOJIBAKE_SEPARATOR_RE.sub(" ", normalized)
    normalized = _LINE_ENDING_RE.sub("\n", normalized)
    normalized = normalized.replace("\u00a0", " ")
    normalized = _HORIZONTAL_SPACE_RE.sub(" ", normalized)
    normalized = _LINE_SPACE_RE.sub("\n", normalized)
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    normalized = _BLANK_LINES_RE.sub("\n\n", normalized)
    return normalized.strip()
