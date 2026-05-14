from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from config import (
    OCR_DET_LIMIT_SIDE_LEN,
    OCR_DROP_SCORE,
    OCR_LANG,
    OCR_QUALITY_MODE,
    OCR_SAVE_PREPROCESSED,
    OCR_TILE_HEIGHT,
    OCR_TILE_MIN_HEIGHT,
    OCR_TILE_MODE,
    OCR_TILE_OVERLAP,
    OCR_USE_ANGLE_CLS,
    OCR_VISUALIZATION_DIR,
    TEMP_DIR,
)
from utils.file_utils import unique_path
from utils.logger import get_logger


logger = get_logger(__name__)

_KOREAN_RE = re.compile(r"[\uac00-\ud7a3]")
_TEXT_RE = re.compile(r"[\uac00-\ud7a3A-Za-z0-9]")
_MOJIBAKE_MARKERS = ("\ufffd", "\u5360", "\ud6c4", "\ud6c2", "\ucc59", "\uca09")


@lru_cache(maxsize=1)
def _get_paddle_ocr() -> Any:
    """Load PaddleOCR lazily so direct-extraction requests do not pay OCR startup cost."""
    try:
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise RuntimeError(
            "PaddleOCR is not installed. Install requirements.txt before running OCR fallback."
        ) from exc

    options = {
        "use_angle_cls": OCR_USE_ANGLE_CLS,
        "lang": OCR_LANG,
        "det_limit_side_len": OCR_DET_LIMIT_SIDE_LEN,
        "drop_score": OCR_DROP_SCORE,
    }

    try:
        return PaddleOCR(**options)
    except TypeError:
        return PaddleOCR(use_angle_cls=OCR_USE_ANGLE_CLS, lang=OCR_LANG)


def _coerce_box(value: Any) -> list[list[float]] | None:
    if value is None:
        return None

    try:
        points = value.tolist()
    except AttributeError:
        points = value

    if not isinstance(points, (list, tuple)):
        return None

    box: list[list[float]] = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return None
        try:
            box.append([float(point[0]), float(point[1])])
        except (TypeError, ValueError):
            return None

    return box if len(box) >= 4 else None


def _parse_confidence(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _parse_line(line: Any) -> dict[str, Any] | None:
    if isinstance(line, (list, tuple)) and len(line) >= 2:
        box = _coerce_box(line[0])
        text_info = line[1]
        if isinstance(text_info, (list, tuple)) and text_info:
            text = str(text_info[0]).strip()
            confidence = _parse_confidence(text_info[1] if len(text_info) > 1 else None)
            if text:
                return {"text": text, "confidence": confidence, "box": box}

    if isinstance(line, dict):
        text = str(line.get("text") or line.get("rec_text") or "").strip()
        confidence = _parse_confidence(line.get("confidence") or line.get("rec_score"))
        box = _coerce_box(
            line.get("box")
            or line.get("points")
            or line.get("poly")
            or line.get("rec_poly")
            or line.get("dt_poly")
        )
        if text:
            return {"text": text, "confidence": confidence, "box": box}

    return None


def _parse_dict_page(page_result: dict[str, Any]) -> list[dict[str, Any]] | None:
    rec_texts = page_result.get("rec_texts")
    if not isinstance(rec_texts, list):
        return None

    rec_scores = page_result.get("rec_scores") or []
    boxes = (
        page_result.get("rec_polys")
        or page_result.get("dt_polys")
        or page_result.get("rec_boxes")
        or page_result.get("boxes")
        or []
    )
    lines: list[dict[str, Any]] = []

    for index, text in enumerate(rec_texts):
        parsed_text = str(text).strip()
        if not parsed_text:
            continue
        score = rec_scores[index] if index < len(rec_scores) else None
        box = boxes[index] if isinstance(boxes, list) and index < len(boxes) else None
        lines.append(
            {
                "text": parsed_text,
                "confidence": _parse_confidence(score),
                "box": _coerce_box(box),
            }
        )

    return lines


def _iter_ocr_lines(raw_result: Any) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []

    if isinstance(raw_result, list):
        for page_result in raw_result:
            if page_result is None:
                continue
            if isinstance(page_result, dict):
                dict_lines = _parse_dict_page(page_result)
                if dict_lines is not None:
                    lines.extend(dict_lines)
                    continue
                parsed_line = _parse_line(page_result)
                if parsed_line:
                    lines.append(parsed_line)
                continue
            if isinstance(page_result, list):
                for line in page_result:
                    parsed_line = _parse_line(line)
                    if parsed_line:
                        lines.append(parsed_line)
                continue
            parsed_line = _parse_line(page_result)
            if parsed_line:
                lines.append(parsed_line)

    return lines


def _read_image_cv2(image_path: Path) -> Any | None:
    import cv2
    import numpy as np

    try:
        data = np.fromfile(str(image_path), dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _write_image_cv2(image_path: Path, image: Any) -> None:
    import cv2

    success, encoded = cv2.imencode(image_path.suffix or ".png", image)
    if not success:
        raise RuntimeError(f"Failed to encode OCR image: {image_path}")
    encoded.tofile(str(image_path))


def _preprocess_candidates(image_path: Path) -> list[dict[str, Any]]:
    candidates = [{"name": "original", "path": image_path, "temporary": False}]
    if OCR_QUALITY_MODE not in {"accurate", "extreme"}:
        return candidates

    try:
        import cv2
    except ImportError:
        logger.warning("opencv-python is not installed; OCR preprocessing is disabled.")
        return candidates

    image = _read_image_cv2(image_path)
    if image is None:
        logger.warning("OpenCV could not read image for preprocessing: %s", image_path)
        return candidates

    output_dir = TEMP_DIR / "ocr_preprocessed" / image_path.parent.name
    output_dir.mkdir(parents=True, exist_ok=True)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    variants = {
        "contrast_sharpen": _sharpen_gray(clahe),
        "adaptive_threshold": cv2.adaptiveThreshold(
            clahe,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            9,
        ),
        "denoise_threshold": _denoise_threshold(clahe),
    }

    if OCR_QUALITY_MODE == "extreme":
        variants["morph_close"] = _morph_close(variants["adaptive_threshold"])

    for name, variant in variants.items():
        output_path = unique_path(output_dir / f"{image_path.stem}_{name}.png")
        _write_image_cv2(output_path, variant)
        candidates.append({"name": name, "path": output_path, "temporary": not OCR_SAVE_PREPROCESSED})

    return candidates


def _sharpen_gray(gray: Any) -> Any:
    import cv2

    blurred = cv2.GaussianBlur(gray, (0, 0), 1.0)
    return cv2.addWeighted(gray, 1.6, blurred, -0.6, 0)


def _denoise_threshold(gray: Any) -> Any:
    import cv2

    denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    return cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]


def _morph_close(binary: Any) -> Any:
    import cv2

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)


def _ocr_image(ocr: Any, image_path: Path) -> list[dict[str, Any]]:
    try:
        raw_result = ocr.ocr(str(image_path), cls=OCR_USE_ANGLE_CLS)
    except TypeError:
        raw_result = ocr.ocr(str(image_path))
    return _iter_ocr_lines(raw_result)


def _text_quality_score(text: str) -> float:
    if not text:
        return 0.0

    text_chars = len(_TEXT_RE.findall(text))
    korean_chars = len(_KOREAN_RE.findall(text))
    mojibake_count = sum(text.count(marker) for marker in _MOJIBAKE_MARKERS)
    punctuation_noise = sum(1 for char in text if not char.isspace() and not _TEXT_RE.match(char))

    return (text_chars * 1.2) + (korean_chars * 0.8) - (mojibake_count * 25) - (punctuation_noise * 0.2)


def _confidence(line: dict[str, Any]) -> float:
    value = line.get("confidence")
    return float(value) if value is not None else 0.0


def _candidate_score(lines: list[dict[str, Any]]) -> float:
    if not lines:
        return 0.0

    text = "\n".join(line["text"] for line in lines)
    scored_lines = [
        (line["text"], float(line["confidence"]))
        for line in lines
        if line.get("confidence") is not None
    ]
    confidences = [confidence for _, confidence in scored_lines]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    weighted_chars = sum(len(text) * (confidence**2) for text, confidence in scored_lines)
    high_confidence_bonus = sum(1 for _, confidence in scored_lines if confidence >= 0.85) * 1.5
    low_confidence_penalty = sum(1 for _, confidence in scored_lines if confidence < 0.65) * 8

    return (
        (weighted_chars * 1.4)
        + (_text_quality_score(text) * 0.35)
        + (avg_confidence * 120)
        + high_confidence_bonus
        - low_confidence_penalty
    )


def _box_bounds(box: list[list[float]] | None) -> tuple[float, float, float, float] | None:
    if not box:
        return None
    xs = [point[0] for point in box]
    ys = [point[1] for point in box]
    return min(xs), min(ys), max(xs), max(ys)


def _offset_box(box: list[list[float]] | None, x_offset: int, y_offset: int) -> list[list[float]] | None:
    if not box:
        return None
    return [[point[0] + x_offset, point[1] + y_offset] for point in box]


def _line_center(line: dict[str, Any]) -> tuple[float, float]:
    bounds = _box_bounds(line.get("box"))
    if not bounds:
        return 0.0, 0.0
    left, top, right, bottom = bounds
    return (left + right) / 2, (top + bottom) / 2


def _box_iou(first: list[list[float]] | None, second: list[list[float]] | None) -> float:
    first_bounds = _box_bounds(first)
    second_bounds = _box_bounds(second)
    if not first_bounds or not second_bounds:
        return 0.0

    left = max(first_bounds[0], second_bounds[0])
    top = max(first_bounds[1], second_bounds[1])
    right = min(first_bounds[2], second_bounds[2])
    bottom = min(first_bounds[3], second_bounds[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    if intersection <= 0:
        return 0.0

    first_area = (first_bounds[2] - first_bounds[0]) * (first_bounds[3] - first_bounds[1])
    second_area = (second_bounds[2] - second_bounds[0]) * (second_bounds[3] - second_bounds[1])
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def _box_overlap_ratio(
    line_box: list[list[float]] | None,
    region_box: tuple[float, float, float, float],
) -> float:
    line_bounds = _box_bounds(line_box)
    if not line_bounds:
        return 0.0

    left = max(line_bounds[0], region_box[0])
    top = max(line_bounds[1], region_box[1])
    right = min(line_bounds[2], region_box[2])
    bottom = min(line_bounds[3], region_box[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    if intersection <= 0:
        return 0.0

    line_area = (line_bounds[2] - line_bounds[0]) * (line_bounds[3] - line_bounds[1])
    if line_area <= 0:
        return 0.0
    return intersection / line_area


def _filter_lines_by_text_regions(
    lines: list[dict[str, Any]],
    text_regions: list[tuple[float, float, float, float]],
    overlap_threshold: float = 0.55,
) -> list[dict[str, Any]]:
    if not text_regions:
        return lines

    filtered: list[dict[str, Any]] = []
    for line in lines:
        overlaps = [
            _box_overlap_ratio(line.get("box"), region)
            for region in text_regions
        ]
        max_overlap = max(overlaps) if overlaps else 0.0
        if max_overlap < overlap_threshold:
            filtered.append(line)
    return filtered


def _deduplicate_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_lines = sorted(lines, key=lambda line: (_confidence(line), len(line.get("text", ""))), reverse=True)
    kept: list[dict[str, Any]] = []

    for line in sorted_lines:
        text = line.get("text", "").strip()
        if not text:
            continue

        duplicate = False
        for existing in kept:
            same_text = text == existing.get("text", "").strip()
            line_x, line_y = _line_center(line)
            existing_x, existing_y = _line_center(existing)
            close_center = abs(line_x - existing_x) <= 12 and abs(line_y - existing_y) <= 12
            if _box_iou(line.get("box"), existing.get("box")) >= 0.35 or (same_text and close_center):
                duplicate = True
                break

        if not duplicate:
            kept.append(line)

    return sorted(kept, key=lambda line: (_line_center(line)[1], _line_center(line)[0]))


def _lines_to_text(lines: list[dict[str, Any]]) -> str:
    ordered = sorted(lines, key=lambda line: (_line_center(line)[1], _line_center(line)[0]))
    rows: list[list[dict[str, Any]]] = []

    for line in ordered:
        bounds = _box_bounds(line.get("box"))
        if not bounds:
            rows.append([line])
            continue

        _, top, _, bottom = bounds
        center_y = (top + bottom) / 2
        height = max(1.0, bottom - top)

        for row in rows:
            row_bounds = [_box_bounds(item.get("box")) for item in row]
            row_bounds = [item for item in row_bounds if item]
            if not row_bounds:
                continue
            row_center_y = sum((item[1] + item[3]) / 2 for item in row_bounds) / len(row_bounds)
            row_height = sum(max(1.0, item[3] - item[1]) for item in row_bounds) / len(row_bounds)
            if abs(center_y - row_center_y) <= max(height, row_height) * 0.55:
                row.append(line)
                break
        else:
            rows.append([line])

    text_rows: list[str] = []
    for row in rows:
        row = sorted(row, key=lambda line: _line_center(line)[0])
        text_rows.append(" ".join(line["text"] for line in row if line.get("text")).strip())

    return "\n".join(row for row in text_rows if row).strip()


def _select_best_ocr_result(ocr: Any, image_path: Path) -> dict[str, Any]:
    candidates = _preprocess_candidates(image_path)
    results: list[dict[str, Any]] = []

    for candidate in candidates:
        logger.info("Running OCR candidate=%s image=%s", candidate["name"], candidate["path"])
        lines = _ocr_image(ocr, candidate["path"])
        text = _lines_to_text(lines) or "\n".join(line["text"] for line in lines).strip()
        score = _candidate_score(lines)
        confidences = [
            float(line["confidence"])
            for line in lines
            if line.get("confidence") is not None
        ]

        results.append(
            {
                "variant": candidate["name"],
                "path": candidate["path"],
                "temporary": candidate["temporary"],
                "lines": lines,
                "text": text,
                "score": score,
                "line_count": len(lines),
                "char_count": len(text),
                "avg_confidence": sum(confidences) / len(confidences) if confidences else None,
            }
        )

    best = max(results, key=lambda result: result["score"])
    for result in results:
        if result["temporary"] and result["path"] != best["path"]:
            Path(result["path"]).unlink(missing_ok=True)

    logger.info(
        "Selected OCR variant=%s score=%.2f lines=%s chars=%s for %s",
        best["variant"],
        best["score"],
        best["line_count"],
        best["char_count"],
        image_path,
    )
    return best


def _tile_image_paths(image_path: Path) -> list[dict[str, Any]]:
    if not OCR_TILE_MODE:
        return []

    image = _read_image_cv2(image_path)
    if image is None:
        return []

    height, width = image.shape[:2]
    if height < OCR_TILE_MIN_HEIGHT or height <= OCR_TILE_HEIGHT:
        return []

    step = max(1, OCR_TILE_HEIGHT - OCR_TILE_OVERLAP)
    output_dir = TEMP_DIR / "ocr_tiles" / image_path.parent.name
    output_dir.mkdir(parents=True, exist_ok=True)

    tiles: list[dict[str, Any]] = []
    top = 0
    index = 1
    while top < height:
        bottom = min(height, top + OCR_TILE_HEIGHT)
        if bottom - top < OCR_TILE_HEIGHT * 0.45 and tiles:
            break

        tile_path = unique_path(output_dir / f"{image_path.stem}_tile_{index:03d}.png")
        _write_image_cv2(tile_path, image[top:bottom, 0:width])
        tiles.append(
            {
                "path": tile_path,
                "x_offset": 0,
                "y_offset": top,
                "height": bottom - top,
                "width": width,
            }
        )

        if bottom >= height:
            break
        top += step
        index += 1

    return tiles


def _run_tiled_ocr(
    ocr: Any,
    image_path: Path,
    text_regions: list[tuple[float, float, float, float]] | None = None,
) -> dict[str, Any]:
    tile_lines: list[dict[str, Any]] = []
    tile_metrics: list[dict[str, Any]] = []

    for tile in _tile_image_paths(image_path):
        tile_result = _select_best_ocr_result(ocr, tile["path"])
        adjusted_lines: list[dict[str, Any]] = []

        for line in tile_result["lines"]:
            adjusted_line = {**line}
            adjusted_line["box"] = _offset_box(line.get("box"), tile["x_offset"], tile["y_offset"])
            adjusted_line["source"] = f"tile:{tile_result['variant']}"
            adjusted_lines.append(adjusted_line)

        adjusted_lines = _filter_lines_by_text_regions(adjusted_lines, text_regions or [])
        tile_lines.extend(adjusted_lines)
        tile_metrics.append(
            {
                "path": str(tile["path"].resolve()),
                "y_offset": tile["y_offset"],
                "height": tile["height"],
                "selected_variant": tile_result["variant"],
                "line_count": len(adjusted_lines),
                "score": tile_result["score"],
            }
        )

        if not OCR_SAVE_PREPROCESSED:
            Path(tile["path"]).unlink(missing_ok=True)

    return {
        "lines": tile_lines,
        "metrics": tile_metrics,
        "tile_count": len(tile_metrics),
    }


def _select_page_ocr_result(
    ocr: Any,
    image_path: Path,
    text_regions: list[tuple[float, float, float, float]] | None = None,
) -> dict[str, Any]:
    full_result = _select_best_ocr_result(ocr, image_path)
    full_result["lines"] = _filter_lines_by_text_regions(full_result["lines"], text_regions or [])
    full_result["text"] = _lines_to_text(full_result["lines"])
    full_result["line_count"] = len(full_result["lines"])
    full_result["char_count"] = len(full_result["text"])
    tiled_result = _run_tiled_ocr(ocr, image_path, text_regions=text_regions)

    if not tiled_result["lines"]:
        full_result["tile_count"] = 0
        full_result["tile_metrics"] = []
        full_result["merged_with_tiles"] = False
        return full_result

    merged_lines = _deduplicate_lines([*full_result["lines"], *tiled_result["lines"]])
    merged_text = _lines_to_text(merged_lines)
    confidence_count = sum(1 for line in merged_lines if line.get("confidence") is not None)

    full_result.update(
        {
            "variant": f"{full_result['variant']}+tiles",
            "lines": merged_lines,
            "text": merged_text,
            "score": _candidate_score(merged_lines),
            "line_count": len(merged_lines),
            "char_count": len(merged_text),
            "avg_confidence": (
                sum(_confidence(line) for line in merged_lines if line.get("confidence") is not None)
                / max(1, confidence_count)
            ),
            "tile_count": tiled_result["tile_count"],
            "tile_metrics": tiled_result["metrics"],
            "merged_with_tiles": True,
        }
    )
    return full_result


def _visualize_ocr_page(
    image_path: Path,
    lines: list[dict[str, Any]],
    page_number: int,
    output_dir: Path = OCR_VISUALIZATION_DIR,
) -> Path | None:
    boxed_lines = [line for line in lines if line.get("box")]
    if not boxed_lines:
        return None

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.warning("Pillow is not installed; skipping OCR visualization.")
        return None

    document_output_dir = output_dir / image_path.parent.name
    document_output_dir.mkdir(parents=True, exist_ok=True)
    output_path = unique_path(document_output_dir / f"page_{page_number:04d}_ocr.png")

    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)

    for index, line in enumerate(boxed_lines, start=1):
        box = line["box"]
        points = [(point[0], point[1]) for point in box]
        confidence = line.get("confidence")
        label = f"{index}"
        if confidence is not None:
            label = f"{index} {confidence:.2f}"

        draw.line(points + [points[0]], fill=(255, 60, 60), width=3)
        x = min(point[0] for point in points)
        y = min(point[1] for point in points)
        label_box = draw.textbbox((x, y), label)
        draw.rectangle(label_box, fill=(255, 60, 60))
        draw.text((x, y), label, fill=(255, 255, 255))

    image.save(output_path)
    logger.info("Saved OCR visualization: %s", output_path)
    return output_path


def run_paddle_ocr_on_images(
    image_paths: list[Path],
    text_exclusion_regions: dict[int, list[tuple[float, float, float, float]]] | None = None,
) -> dict[str, Any]:
    """Run PaddleOCR on rendered page images and return text, boxes, and visualizations."""
    ocr = _get_paddle_ocr()
    pages: list[dict[str, Any]] = []
    all_text: list[str] = []
    visualization_paths: list[str] = []

    for page_number, image_path in enumerate(image_paths, start=1):
        image_path = image_path.resolve()
        if not image_path.exists():
            raise FileNotFoundError(f"OCR image not found: {image_path}")

        regions = (text_exclusion_regions or {}).get(page_number, [])
        best_result = _select_page_ocr_result(ocr, image_path, text_regions=regions)
        lines = best_result["lines"]
        page_text = best_result["text"]
        visualization_path = _visualize_ocr_page(image_path, lines, page_number)

        if visualization_path:
            visualization_paths.append(str(visualization_path.resolve()))

        pages.append(
            {
                "page": page_number,
                "image_path": str(image_path),
                "visualization_path": str(visualization_path.resolve()) if visualization_path else None,
                "text": page_text,
                "selected_variant": best_result["variant"],
                "candidate_score": best_result["score"],
                "candidate_metrics": {
                    "line_count": best_result["line_count"],
                    "char_count": best_result["char_count"],
                    "avg_confidence": best_result["avg_confidence"],
                    "tile_count": best_result.get("tile_count", 0),
                    "merged_with_tiles": best_result.get("merged_with_tiles", False),
                },
                "tile_metrics": best_result.get("tile_metrics", []),
                "lines": lines,
            }
        )
        if page_text:
            all_text.append(page_text)

    extracted_text = "\n\n".join(all_text).strip()
    logger.info("PaddleOCR completed for %s images, chars=%s", len(image_paths), len(extracted_text))
    return {
        "engine": "paddleocr",
        "lang": OCR_LANG,
        "quality_mode": OCR_QUALITY_MODE,
        "det_limit_side_len": OCR_DET_LIMIT_SIDE_LEN,
        "drop_score": OCR_DROP_SCORE,
        "tile_mode": OCR_TILE_MODE,
        "tile_height": OCR_TILE_HEIGHT,
        "tile_overlap": OCR_TILE_OVERLAP,
        "page_count": len(image_paths),
        "text": extracted_text,
        "pages": pages,
        "visualization_paths": visualization_paths,
    }
