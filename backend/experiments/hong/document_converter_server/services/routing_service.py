from __future__ import annotations

from pathlib import Path
from typing import Any

from config import LOG_FILE, TEXT_OUTPUT_DIR
from converters.docx_parser import parse_docx_text
from converters.hwp_converter import convert_hwp_to_pdf
from converters.hwpx_parser import parse_hwpx_text
from converters.image_converter import convert_image_to_pdf
from converters.pdf_converter import render_pdf_to_images
from router.document_router import determine_document_route
from services.ocr_service import run_paddle_ocr_on_images
from utils.file_utils import write_text_file
from utils.logger import get_logger


logger = get_logger(__name__)


def _paths_to_strings(paths: list[Path]) -> list[str]:
    return [str(path.resolve()) for path in paths]


def _write_extracted_text(source_path: Path, text: str) -> Path:
    TEXT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = TEXT_OUTPUT_DIR / f"{source_path.stem}.txt"
    write_text_file(output_path, text)
    return output_path


def _base_result(source_path: Path, route: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "converted",
        "source_file": str(source_path.resolve()),
        "source_extension": source_path.suffix.lower(),
        "log_file": str(LOG_FILE.resolve()),
        "route": {
            "strategy": route["strategy"],
            "reason": route["reason"],
            "ocr_required": route["ocr_required"],
            "text_length": route["text_length"],
            "metadata": route["metadata"],
        },
    }


def _direct_text_result(source_path: Path, route: dict[str, Any], text: str) -> dict[str, Any]:
    text_path = _write_extracted_text(source_path, text)
    return {
        **_base_result(source_path, route),
        "conversion_type": route["strategy"],
        "pdf_path": None,
        "image_paths": [],
        "text_path": str(text_path.resolve()),
        "extracted_text": text,
        "ocr_required": False,
    }


def _ocr_ready_result(
    source_path: Path,
    route: dict[str, Any],
    *,
    pdf_path: Path,
    image_paths: list[Path],
) -> dict[str, Any]:
    ocr_result = run_paddle_ocr_on_images(image_paths)
    text_path = _write_extracted_text(source_path, ocr_result["text"])

    return {
        **_base_result(source_path, route),
        "conversion_type": route["strategy"],
        "pdf_path": str(pdf_path.resolve()),
        "image_paths": _paths_to_strings(image_paths),
        "text_path": str(text_path.resolve()),
        "extracted_text": ocr_result["text"],
        "ocr_required": True,
        "ocr_status": "completed",
        "ocr_result": ocr_result,
    }


def _hwp_direct_text_with_ocr_result(
    source_path: Path,
    route: dict[str, Any],
    *,
    pdf_path: Path,
    image_paths: list[Path],
) -> dict[str, Any]:
    direct_text = (route.get("extracted_text") or "").strip()
    ocr_result = run_paddle_ocr_on_images(image_paths)
    ocr_text = ocr_result["text"].strip()

    text_parts = []
    if direct_text:
        text_parts.append("[DIRECT_TEXT]\n" + direct_text)
    if ocr_text:
        text_parts.append("[OCR_TEXT]\n" + ocr_text)

    merged_text = "\n\n".join(text_parts).strip()
    text_path = _write_extracted_text(source_path, merged_text)

    return {
        **_base_result(source_path, route),
        "conversion_type": route["strategy"],
        "pdf_path": str(pdf_path.resolve()),
        "image_paths": _paths_to_strings(image_paths),
        "text_path": str(text_path.resolve()),
        "extracted_text": merged_text,
        "direct_text": direct_text,
        "ocr_text": ocr_text,
        "ocr_required": True,
        "ocr_status": "completed",
        "ocr_result": ocr_result,
    }


def process_document_with_routing(source_path: Path, render_scale: float) -> dict[str, Any]:
    """Run the hybrid document pipeline selected by document routing."""
    source_path = source_path.resolve()
    route = determine_document_route(source_path)
    strategy = route["strategy"]

    logger.info("Selected document route: %s for %s", strategy, source_path)

    if strategy == "pdf_direct_text":
        return _direct_text_result(source_path, route, route["extracted_text"] or "")

    if strategy == "hwpx_xml_parser":
        text = parse_hwpx_text(source_path)
        return _direct_text_result(source_path, route, text)

    if strategy == "docx_parser":
        text = parse_docx_text(source_path)
        return _direct_text_result(source_path, route, text)

    if strategy == "hwp_direct_text_with_ocr":
        pdf_path = convert_hwp_to_pdf(source_path)
        image_paths = render_pdf_to_images(pdf_path, scale=render_scale)
        return _hwp_direct_text_with_ocr_result(
            source_path,
            route,
            pdf_path=pdf_path,
            image_paths=image_paths,
        )

    if strategy == "pdf_ocr_fallback":
        image_paths = render_pdf_to_images(source_path, scale=render_scale)
        return _ocr_ready_result(source_path, route, pdf_path=source_path, image_paths=image_paths)

    if strategy == "hwp_to_pdf_ocr_fallback":
        pdf_path = convert_hwp_to_pdf(source_path)
        image_paths = render_pdf_to_images(pdf_path, scale=render_scale)
        return _ocr_ready_result(source_path, route, pdf_path=pdf_path, image_paths=image_paths)

    if strategy == "image_to_pdf_ocr":
        pdf_path = convert_image_to_pdf(source_path)
        image_paths = render_pdf_to_images(pdf_path, scale=render_scale)
        return _ocr_ready_result(source_path, route, pdf_path=pdf_path, image_paths=image_paths)

    raise ValueError(f"Unsupported document route strategy: {strategy}")
