from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from utils.logger import get_logger


logger = get_logger(__name__)


_SPACE_RE = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = _SPACE_RE.sub(" ", text)
    text = re.sub(r" *\n *", "\n", text)
    return _BLANK_LINES_RE.sub("\n\n", text).strip()


def _iter_section_xml_names(zip_file: zipfile.ZipFile) -> list[str]:
    names = zip_file.namelist()
    section_names = [
        name
        for name in names
        if name.lower().endswith(".xml")
        and (
            "section" in Path(name).name.lower()
            or "section" in name.lower()
            or "bodytext" in name.lower()
        )
    ]
    return sorted(section_names)


def _paragraph_text(paragraph: ElementTree.Element) -> str:
    parts: list[str] = []
    for node in paragraph.iter():
        tag = _strip_namespace(node.tag)
        if tag in {"script", "style", "header", "footer"}:
            continue
        if node.text:
            parts.append(node.text)
        if tag in {"lineBreak", "br"}:
            parts.append("\n")
        if node.tail:
            parts.append(node.tail)
    return _normalize_text("".join(parts))


def _extract_text_from_xml(xml_bytes: bytes) -> list[str]:
    root = ElementTree.fromstring(xml_bytes)
    paragraphs: list[str] = []

    for element in root.iter():
        tag = _strip_namespace(element.tag)
        if tag in {"p", "paragraph"}:
            paragraph = _paragraph_text(element)
            if paragraph:
                paragraphs.append(paragraph)

    if paragraphs:
        return paragraphs

    fallback = _normalize_text("".join(root.itertext()))
    return [fallback] if fallback else []


def parse_hwpx_text(source_path: Path) -> str:
    """Extract text from HWPX without OCR by reading XML inside the archive."""
    source_path = source_path.resolve()
    if source_path.suffix.lower() != ".hwpx":
        raise ValueError("HWPX 파서는 .hwpx 파일만 처리합니다.")
    if not source_path.exists():
        raise FileNotFoundError(f"HWPX 파일을 찾을 수 없습니다: {source_path}")
    if not zipfile.is_zipfile(source_path):
        raise ValueError("HWPX 파일이 ZIP/XML 기반 문서 형식이 아닙니다.")

    paragraphs: list[str] = []
    with zipfile.ZipFile(source_path) as archive:
        section_names = _iter_section_xml_names(archive)
        if not section_names:
            section_names = sorted(name for name in archive.namelist() if name.lower().endswith(".xml"))

        logger.info("Parsing HWPX XML sections: %s", section_names)
        for name in section_names:
            try:
                paragraphs.extend(_extract_text_from_xml(archive.read(name)))
            except ElementTree.ParseError:
                logger.warning("Skipping malformed XML in HWPX: %s", name)

    return _normalize_text("\n\n".join(paragraphs))
