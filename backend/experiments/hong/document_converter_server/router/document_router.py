from __future__ import annotations

from pathlib import Path
from typing import Any

from config import DIRECT_TEXT_MIN_CHARS, HWP_OCR_SUPPLEMENT, IMAGE_EXTENSIONS
from converters.hwp_converter import detect_hwp_has_images, extract_hwp_text
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
        extraction_method: str | None = None
        extraction_error: str | None = None
        has_images = bool(HWP_OCR_SUPPLEMENT)
        has_images_detection_error: str | None = None
        if not has_images:
            try:
                has_images = detect_hwp_has_images(source_path)
            except Exception as exc:
                has_images_detection_error = str(exc)
                logger.warning("HWP image detection failed, continue with fallback-safe routing: %s", exc)

        try:
            text = extract_hwp_text(source_path)
            if _text_is_enough(text, text_threshold):
                extraction_method = "direct"  # COM or OLE succeeded

                if not has_images:
                    return _route(
                        extension=extension,
                        strategy="hwp_direct_text",
                        reason=(
                            "HWP direct text extraction returned enough text; "
                            "no embedded images detected."
                        ),
                        ocr_required=False,
                        extracted_text=text,
                        metadata={
                            "threshold": text_threshold,
                            "direct_text_available": True,
                            "has_images": False,
                            "reason_code": "direct_extraction_success",
                            "extraction_method": extraction_method,
                            "has_images_detection_error": has_images_detection_error,
                        },
                    )

                return _route(
                    extension=extension,
                    strategy="hwp_direct_text_with_ocr",
                    reason=(
                        "HWP direct text extraction succeeded and embedded images "
                        "were detected; convert to PDF and run OCR to supplement."
                    ),
                    ocr_required=True,
                    extracted_text=text,
                    metadata={
                        "threshold": text_threshold,
                        "direct_text_available": True,
                            "has_images": True,
                            "reason_code": "image_or_scan_likely",
                            "extraction_method": extraction_method,
                            "has_images_detection_error": has_images_detection_error,
                        },
                    )
            else:
                # Text was extracted but below threshold.
                extraction_method = "direct"
                extraction_error = f"extracted only {len(text.strip())} chars (threshold={text_threshold})"
        except Exception as exc:
            extraction_error = str(exc)
            logger.warning("HWP direct text extraction unavailable, using fallback: %s", exc)

        # Determine the specific reason code for the fallback.
        if extraction_method == "direct" and extraction_error:
            reason_code = "text_not_found"
        else:
            reason_code = "direct_extraction_failed"

        return _route(
            extension=extension,
            strategy="hwp_to_pdf_ocr_fallback",
            reason="HWP direct extraction failed or had too little text; convert to PDF for OCR fallback.",
            ocr_required=True,
            metadata={
                "threshold": text_threshold,
                "reason_code": reason_code,
                "extraction_error": extraction_error,
                "has_images": has_images,
                "has_images_detection_error": has_images_detection_error,
            },
        )

    if extension in IMAGE_EXTENSIONS:
        return _route(
            extension=extension,
            strategy="image_to_pdf_ocr",
            reason="Uploaded image is converted to PDF, rendered, and processed with PaddleOCR.",
            ocr_required=True,
        )

    raise ValueError(f"Unsupported file extension: {extension}")
