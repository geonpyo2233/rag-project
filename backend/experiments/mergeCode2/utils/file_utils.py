from __future__ import annotations

import re
from pathlib import Path


_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(filename: str) -> str:
    """Return a Windows-safe filename while preserving the extension."""
    cleaned = _INVALID_FILENAME_CHARS.sub("_", filename).strip().strip(".")
    if not cleaned:
        return "uploaded_document"
    return cleaned[:180]


def unique_path(path: Path) -> Path:
    """Return a non-existing path by appending a numeric suffix if needed."""
    path = path.resolve()
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 1
    while True:
        candidate = parent / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def write_text_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")

