from __future__ import annotations

from pathlib import Path
from typing import Any

from config import DIRECT_TEXT_MIN_CHARS, IMAGE_EXTENSIONS
from converters.hwp_converter import extract_hwp_text
from converters.pdf_converter import extract_pdf_text
from utils.logger import get_logger


logger = get_logger(__name__)


def _text_is_enough(text: str, threshold: int) -> bool:
    return len(text.strip()) >= threshold


def _route(
    *,
    extension: str,
    strategy: str,
    reason: str,
    ocr_required: bool,
    extracted_text: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "extension": extension,
        "strategy": strategy,
        "reason": reason,
        "ocr_required": ocr_required,
        "text_length": len((extracted_text or "").strip()),
        "extracted_text": extracted_text,
        "metadata": metadata or {},
    }


def determine_document_route(
    source_path: Path,
    text_threshold: int = DIRECT_TEXT_MIN_CHARS,
) -> dict[str, Any]:
    """Decide parser/direct extraction/OCR fallback strategy for a document."""
    source_path = source_path.resolve()
    extension = source_path.suffix.lower()

    if not source_path.exists():
        raise FileNotFoundError(f"Uploaded file not found: {source_path}")

    logger.info("Analyzing document route: %s", source_path)

    if extension == ".hwpx":
        return _route(
            extension=extension,
            strategy="hwpx_xml_parser",
            reason="HWPX is a ZIP/XML document and must be parsed directly without OCR.",
            ocr_required=False,
        )

    if extension == ".docx":
        return _route(
            extension=extension,
            strategy="docx_parser",
            reason="DOCX has accessible document XML and can be parsed directly.",
            ocr_required=False,
        )

    if extension == ".pdf":
        text = extract_pdf_text(source_path)
        if _text_is_enough(text, text_threshold):
            return _route(
                extension=extension,
                strategy="pdf_direct_text",
                reason="PDF contains enough embedded text for direct extraction.",
                ocr_required=False,
                extracted_text=text,
                metadata={"threshold": text_threshold},
            )

        return _route(
            extension=extension,
            strategy="pdf_ocr_fallback",
            reason="PDF embedded text is missing or below threshold; OCR fallback is required.",
            ocr_required=True,
            extracted_text=text,
            metadata={"threshold": text_threshold},
        )

    if extension == ".hwp":
        try:
            text = extract_hwp_text(source_path)
            if _text_is_enough(text, text_threshold):
                return _route(
                    extension=extension,
                    strategy="hwp_direct_text_with_ocr",
                    reason=(
                        "HWP direct text extraction succeeded, but HWP may contain "
                        "embedded images; convert to PDF and run PaddleOCR as a supplement."
                    ),
                    ocr_required=True,
                    extracted_text=text,
                    metadata={"threshold": text_threshold, "direct_text_available": True},
                )
        except Exception as exc:
            logger.warning("HWP direct text extraction unavailable, using fallback: %s", exc)

        return _route(
            extension=extension,
            strategy="hwp_to_pdf_ocr_fallback",
            reason="HWP direct extraction failed or had too little text; convert to PDF for OCR fallback.",
            ocr_required=True,
            metadata={"threshold": text_threshold},
        )

    if extension in IMAGE_EXTENSIONS:
        return _route(
            extension=extension,
            strategy="image_to_pdf_ocr",
            reason="Uploaded image is converted to PDF, rendered, and processed with PaddleOCR.",
            ocr_required=True,
        )

    raise ValueError(f"Unsupported file extension: {extension}")
