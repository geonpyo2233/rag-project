from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from config import OCR_LANG, OCR_USE_ANGLE_CLS
from utils.logger import get_logger


logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _get_paddle_ocr() -> Any:
    """Load PaddleOCR lazily so direct-extraction requests do not pay OCR startup cost."""
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError(
            "PaddleOCR is not installed. Install requirements.txt before running OCR fallback."
        ) from exc

    try:
        return PaddleOCR(use_angle_cls=OCR_USE_ANGLE_CLS, lang=OCR_LANG)
    except TypeError:
        # PaddleOCR versions differ in constructor flags. Keep startup tolerant.
        return PaddleOCR(lang=OCR_LANG)


def _parse_line(line: Any) -> tuple[str, float | None]:
    if isinstance(line, (list, tuple)) and len(line) >= 2:
        text_info = line[1]
        if isinstance(text_info, (list, tuple)) and text_info:
            text = str(text_info[0]).strip()
            confidence = None
            if len(text_info) > 1:
                try:
                    confidence = float(text_info[1])
                except (TypeError, ValueError):
                    confidence = None
            return text, confidence

    if isinstance(line, dict):
        text = str(line.get("text") or line.get("rec_text") or "").strip()
        confidence_value = line.get("confidence") or line.get("rec_score")
        try:
            confidence = float(confidence_value) if confidence_value is not None else None
        except (TypeError, ValueError):
            confidence = None
        return text, confidence

    return "", None


def _iter_ocr_lines(raw_result: Any) -> list[tuple[str, float | None]]:
    lines: list[tuple[str, float | None]] = []

    if isinstance(raw_result, list):
        for page_result in raw_result:
            if page_result is None:
                continue
            if isinstance(page_result, dict):
                rec_texts = page_result.get("rec_texts")
                rec_scores = page_result.get("rec_scores") or []
                if isinstance(rec_texts, list):
                    for index, text in enumerate(rec_texts):
                        score = rec_scores[index] if index < len(rec_scores) else None
                        try:
                            confidence = float(score) if score is not None else None
                        except (TypeError, ValueError):
                            confidence = None
                        lines.append((str(text).strip(), confidence))
                    continue
            if isinstance(page_result, list):
                for line in page_result:
                    lines.append(_parse_line(line))
                continue
            lines.append(_parse_line(page_result))

    return [(text, confidence) for text, confidence in lines if text]


def run_paddle_ocr_on_images(image_paths: list[Path]) -> dict[str, Any]:
    """Run PaddleOCR on rendered page images and return text plus page details."""
    ocr = _get_paddle_ocr()
    pages: list[dict[str, Any]] = []
    all_text: list[str] = []

    for page_number, image_path in enumerate(image_paths, start=1):
        image_path = image_path.resolve()
        if not image_path.exists():
            raise FileNotFoundError(f"OCR image not found: {image_path}")

        logger.info("Running PaddleOCR on image: %s", image_path)
        try:
            raw_result = ocr.ocr(str(image_path), cls=OCR_USE_ANGLE_CLS)
        except TypeError:
            raw_result = ocr.ocr(str(image_path))
        lines = _iter_ocr_lines(raw_result)
        page_text = "\n".join(text for text, _ in lines).strip()

        pages.append(
            {
                "page": page_number,
                "image_path": str(image_path),
                "text": page_text,
                "lines": [
                    {"text": text, "confidence": confidence}
                    for text, confidence in lines
                ],
            }
        )
        if page_text:
            all_text.append(page_text)

    extracted_text = "\n\n".join(all_text).strip()
    logger.info("PaddleOCR completed for %s images, chars=%s", len(image_paths), len(extracted_text))
    return {
        "engine": "paddleocr",
        "lang": OCR_LANG,
        "page_count": len(image_paths),
        "text": extracted_text,
        "pages": pages,
    }
