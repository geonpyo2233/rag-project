from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
from paddleocr import PaddleOCR
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def _normalize_for_dedup(text: str) -> str:
    t = re.sub(r"\s+", "", text.strip().lower())
    return re.sub(r"[^0-9a-z\uac00-\ud7a3]", "", t)


def _is_valid_text_shape_weak(text: str) -> bool:
    s = text.strip()
    if not s:
        return False
    compact = re.sub(r"\s+", "", s)
    if not compact:
        return False
    total = len(compact)
    core = sum(1 for ch in compact if ch.isdigit() or ("a" <= ch.lower() <= "z") or ("\uac00" <= ch <= "\ud7a3"))
    symbol_ratio = (total - core) / max(1, total)
    return symbol_ratio <= 0.65


def _weak_postprocess_lines(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered = [ln for ln in lines if _is_valid_text_shape_weak(str(ln.get("text", "")))]
    best_by_key: dict[str, dict[str, Any]] = {}
    for ln in filtered:
        text = str(ln.get("text", "")).strip()
        if not text:
            continue
        key = _normalize_for_dedup(text)
        if len(key) < 2:
            continue
        prev = best_by_key.get(key)
        if prev is None or float(ln.get("confidence", 0.0)) > float(prev.get("confidence", 0.0)):
            best_by_key[key] = ln
    return list(best_by_key.values())


def _box_metrics(box: list[list[float]]) -> tuple[float, float, float]:
    xs = [float(p[0]) for p in box]
    ys = [float(p[1]) for p in box]
    x_min = min(xs)
    y_min = min(ys)
    y_max = max(ys)
    return x_min, (y_min + y_max) / 2.0, (y_max - y_min)


def _reconstruct_lines_from_boxes(raw_lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not raw_lines:
        return []
    heights = [max(1.0, float(item.get("h", 1.0))) for item in raw_lines]
    avg_h = sum(heights) / max(1, len(heights))
    y_threshold = max(10.0, avg_h * 0.6)
    sorted_items = sorted(raw_lines, key=lambda x: float(x["y_center"]))

    groups: list[list[dict[str, Any]]] = []
    for item in sorted_items:
        placed = False
        for group in groups:
            group_y = sum(float(g["y_center"]) for g in group) / len(group)
            if abs(float(item["y_center"]) - group_y) <= y_threshold:
                group.append(item)
                placed = True
                break
        if not placed:
            groups.append([item])

    merged: list[dict[str, Any]] = []
    for group in groups:
        group_sorted = sorted(group, key=lambda x: float(x["x_min"]))
        text = " ".join(str(g["text"]).strip() for g in group_sorted if str(g["text"]).strip())
        if not text:
            continue
        conf = sum(float(g["confidence"]) for g in group_sorted) / max(1, len(group_sorted))
        merged.append({"text": text, "confidence": conf})
    return merged


def _tokenize_for_vote(text: str) -> list[str]:
    return [tok for tok in re.split(r"\s+", text.strip()) if tok]


def _consensus_lines(candidates: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    if not candidates:
        return []
    max_lines = max(len(c) for c in candidates)
    merged: list[dict[str, Any]] = []
    for line_idx in range(max_lines):
        line_texts: list[tuple[list[str], float]] = []
        for cand in candidates:
            if line_idx >= len(cand):
                continue
            text = str(cand[line_idx].get("text", "")).strip()
            conf = float(cand[line_idx].get("confidence", 0.0))
            toks = _tokenize_for_vote(text)
            if toks:
                line_texts.append((toks, conf))
        if not line_texts:
            continue
        max_tok = max(len(toks) for toks, _ in line_texts)
        chosen_tokens: list[str] = []
        conf_acc = 0.0
        conf_cnt = 0
        for tok_idx in range(max_tok):
            votes: dict[str, tuple[int, float]] = {}
            for toks, conf in line_texts:
                if tok_idx >= len(toks):
                    continue
                tok = toks[tok_idx]
                count, score = votes.get(tok, (0, 0.0))
                votes[tok] = (count + 1, score + conf)
            if not votes:
                continue
            best_tok = max(votes.items(), key=lambda kv: (kv[1][0], kv[1][1]))[0]
            chosen_tokens.append(best_tok)
            conf_acc += votes[best_tok][1] / max(1, votes[best_tok][0])
            conf_cnt += 1
        if chosen_tokens:
            merged.append({"text": " ".join(chosen_tokens), "confidence": conf_acc / max(1, conf_cnt)})
    return merged


def _build_variants(image_path: Path) -> dict[str, np.ndarray]:
    with Image.open(image_path) as im:
        base = im.convert("RGB")
    original = np.array(base)
    contrast = np.array(ImageEnhance.Contrast(base).enhance(1.8))
    gray = ImageOps.grayscale(base)
    garr = np.array(gray)
    th = int(max(80, min(190, float(garr.mean()))))
    bin_arr = np.where(garr > th, 255, 0).astype(np.uint8)
    binarized = np.array(Image.fromarray(bin_arr, mode="L").convert("RGB"))
    sharpen = np.array(base.filter(ImageFilter.UnsharpMask(radius=1.8, percent=180, threshold=2)))
    return {"original": original, "contrast": contrast, "binarized": binarized, "sharpen": sharpen}


class OCRService:
    def __init__(self) -> None:
        self._ocr = PaddleOCR(
            use_doc_orientation_classify=False,
            lang="korean",
            show_log=False,
            det_limit_side_len=3200,
            drop_score=0.3,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            engine="paddle",
        )

    def ocr_image(self, image_path: Path) -> str:
        variants = _build_variants(image_path)
        variant_lines: list[list[dict[str, Any]]] = []

        for arr in variants.values():
            raw = self._ocr.ocr(arr, cls=False)
            if not raw or raw[0] is None:
                continue
            tokens: list[dict[str, Any]] = []
            for item in raw[0] or []:
                if item is None or len(item) < 2 or item[1] is None:
                    continue
                box = item[0]
                text = str(item[1][0]).strip()
                conf = float(item[1][1])
                if text:
                    x_min, y_center, h = _box_metrics(box)
                    tokens.append({"text": text, "confidence": conf, "x_min": x_min, "y_center": y_center, "h": h})
            reconstructed = _reconstruct_lines_from_boxes(tokens)
            if reconstructed:
                variant_lines.append(reconstructed)

        consensus = _consensus_lines(variant_lines)
        post_lines = _weak_postprocess_lines(consensus)
        return "\n".join(str(ln["text"]) for ln in post_lines if ln.get("text")).strip()

    def ocr_images(self, image_paths: list[Path]) -> str:
        texts = [self.ocr_image(p) for p in image_paths]
        return "\n".join(t for t in texts if t).strip()

    def ocr_images_map(self, image_paths: list[Path]) -> dict[str, str]:
        """이미지 절대경로 -> OCR 텍스트 맵."""
        result: dict[str, str] = {}
        for path in image_paths:
            text = self.ocr_image(path).strip()
            result[str(path.resolve())] = text
        return result
