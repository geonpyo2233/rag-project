from __future__ import annotations

import re
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
from services.text_postprocess_service import normalize_extracted_text
from utils.file_utils import write_text_file
from utils.logger import get_logger


logger = get_logger(__name__)


def _paths_to_strings(paths: list[Path]) -> list[str]:
    return [str(path.resolve()) for path in paths]


def _extract_pdf_text_regions(
    pdf_path: Path,
    pad: float = 2.0,
) -> dict[int, list[tuple[float, float, float, float]]]:
    """Extract text-layer bounding regions from a PDF for page-wise OCR exclusion."""
    import fitz

    regions_by_page: dict[int, list[tuple[float, float, float, float]]] = {}
    with fitz.open(pdf_path) as document:
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            words = page.get_text("words")  # x0, y0, x1, y1, "word", ...
            regions: list[tuple[float, float, float, float]] = []
            for word in words:
                x0, y0, x1, y1 = word[:4]
                regions.append((x0 - pad, y0 - pad, x1 + pad, y1 + pad))
            regions_by_page[page_index + 1] = regions
    return regions_by_page


def _normalize_for_compare(text: str) -> str:
    """Normalize text for loose duplicate detection between direct text and OCR lines."""
    text = text.lower().strip()
    # Keep Korean/English/digits only for robust comparison.
    text = re.sub(r"[^0-9a-z\uac00-\ud7a3]", "", text)
    return text


def _is_high_quality_ocr_line(
    text: str,
    *,
    min_alpha_num_ratio: float = 0.55,
    max_symbol_ratio: float = 0.35,
) -> bool:
    stripped = text.strip()
    if not stripped:
        return False

    # Remove spaces for ratio calculations.
    compact = "".join(ch for ch in stripped if not ch.isspace())
    if not compact:
        return False

    total = len(compact)
    alpha_num = sum(1 for ch in compact if ch.isalnum() or ("\uac00" <= ch <= "\ud7a3"))
    symbol_count = total - alpha_num

    alpha_num_ratio = alpha_num / total
    symbol_ratio = symbol_count / total
    return alpha_num_ratio >= min_alpha_num_ratio and symbol_ratio <= max_symbol_ratio


def _collect_ocr_supplement_text(
    direct_text: str,
    ocr_result: dict[str, Any],
    min_confidence: float = 0.75,
) -> str:
    """Extract only OCR lines that are not already covered by direct text."""
    normalized_direct = _normalize_for_compare(direct_text)
    if not normalized_direct:
        return normalize_extracted_text(ocr_result.get("text", ""))

    kept_lines: list[str] = []
    seen: set[str] = set()

    for page in ocr_result.get("pages", []):
        for line in page.get("lines", []):
            text = str(line.get("text") or "").strip()
            if not text:
                continue

            confidence_value = line.get("confidence")
            if confidence_value is not None:
                try:
                    if float(confidence_value) < min_confidence:
                        continue
                except (TypeError, ValueError):
                    pass

            normalized_line = _normalize_for_compare(text)
            if len(normalized_line) < 3:
                continue
            if not _is_high_quality_ocr_line(text):
                continue
            if normalized_line in seen:
                continue
            if normalized_line in normalized_direct:
                continue

            seen.add(normalized_line)
            kept_lines.append(text)

    return normalize_extracted_text("\n".join(kept_lines))


def _write_extracted_text(source_path: Path, text: str) -> Path:
    TEXT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = TEXT_OUTPUT_DIR / f"{source_path.stem}.txt"
    write_text_file(output_path, normalize_extracted_text(text))
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
    normalized_text = normalize_extracted_text(text)
    text_path = _write_extracted_text(source_path, normalized_text)
    return {
        **_base_result(source_path, route),
        "conversion_type": route["strategy"],
        "pdf_path": None,
        "image_paths": [],
        "text_path": str(text_path.resolve()),
        "extracted_text": normalized_text,
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
    normalized_text = normalize_extracted_text(ocr_result["text"])
    text_path = _write_extracted_text(source_path, normalized_text)

    return {
        **_base_result(source_path, route),
        "conversion_type": route["strategy"],
        "pdf_path": str(pdf_path.resolve()),
        "image_paths": _paths_to_strings(image_paths),
        "text_path": str(text_path.resolve()),
        "extracted_text": normalized_text,
        "ocr_required": True,
        "ocr_status": "completed",
        "ocr_result": ocr_result,
        "visualization_paths": ocr_result.get("visualization_paths", []),
    }


def _hwp_direct_text_with_ocr_result(
    source_path: Path,
    route: dict[str, Any],
    *,
    pdf_path: Path,
    image_paths: list[Path],
) -> dict[str, Any]:
    direct_text = normalize_extracted_text(route.get("extracted_text") or "")
    text_regions = _extract_pdf_text_regions(pdf_path)
    ocr_result = run_paddle_ocr_on_images(
        image_paths,
        text_exclusion_regions=text_regions,
    )
    # Keep OCR as supplement only: lines already present in direct text are removed.
    ocr_text = _collect_ocr_supplement_text(direct_text, ocr_result)

    text_parts = []
    if direct_text:
        text_parts.append("[DIRECT_TEXT]\n" + direct_text)
    if ocr_text:
        text_parts.append("[OCR_TEXT]\n" + ocr_text)

    merged_text = normalize_extracted_text("\n\n".join(text_parts))
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
        "visualization_paths": ocr_result.get("visualization_paths", []),
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

    if strategy == "hwp_direct_text":
        return _direct_text_result(source_path, route, route["extracted_text"] or "")

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
