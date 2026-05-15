from __future__ import annotations

"""객체 이미지에 대해 PaddleOCR를 실행하는 모듈.

정책:
- 1차 OCR은 기본 호출(ocr.ocr(path)) 사용
- 후처리는 약하게 적용(극단 노이즈 제거 + 중복 제거)
"""

import re
from pathlib import Path
from typing import Any

import numpy as np
from paddleocr import PaddleOCR
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def _normalize_for_dedup(text: str) -> str:
    """중복 판정용 정규화: 공백/기호를 줄여 유사 문자열을 같은 키로 맞춘다."""
    t = re.sub(r"\s+", "", text.strip().lower())
    t = re.sub(r"[^0-9a-z\uac00-\ud7a3]", "", t)
    return t


def _is_valid_text_shape_weak(text: str) -> bool:
    """약한 형태 필터: 특수문자 비율이 과도한 텍스트만 제거한다."""
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
    """약한 후처리.

    1) 극단 노이즈 라인 제거
    2) 유사 라인 중 confidence 높은 라인만 유지
    """
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


def _build_variants(image_path: Path) -> dict[str, np.ndarray]:
    """원본/대비/이진화/샤프닝 전처리 이미지를 만든다."""
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
    return {
        "original": original,
        "contrast": contrast,
        "binarized": binarized,
        "sharpen": sharpen,
    }


def _reconstruct_lines_from_boxes(raw_lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """bbox 기준으로 같은 행을 재구성한다.

    - y 중심값이 가까운 토큰끼리 같은 줄로 묶고
    - 줄 내부는 x 좌표 기준으로 정렬해 문장을 복원한다.
    """
    if not raw_lines:
        return []

    heights = [max(1.0, float(item.get("h", 1.0))) for item in raw_lines]
    avg_h = sum(heights) / max(1, len(heights))
    y_threshold = max(10.0, avg_h * 0.6)

    # y 기준으로 먼저 정렬
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
    """다중 OCR 결과를 줄/토큰 단위로 합의한다.

    - 같은 줄 인덱스끼리 토큰 투표
    - 득표 수 우선, 동률이면 confidence 합이 큰 토큰 선택
    """
    if not candidates:
        return []
    max_lines = max(len(c) for c in candidates)
    merged: list[dict[str, Any]] = []

    for line_idx in range(max_lines):
        # 줄 후보 모으기
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
            merged.append(
                {
                    "text": " ".join(chosen_tokens),
                    "confidence": conf_acc / max(1, conf_cnt),
                }
            )
    return merged


def run_ocr_on_object_images(image_paths: list[Path], lang: str = "korean+en") -> dict[str, Any]:
    """객체 이미지 리스트에 OCR을 수행해 페이지별 결과/병합 텍스트를 반환한다."""
    # 기존 단일 엔진 설정 (요청으로 주석 처리)
    # ocr = PaddleOCR(
    #     use_angle_cls=True,
    #     lang=lang,
    #     show_log=False,
    #     det_limit_side_len=3200,
    #     drop_score=0.3,
    # )

    # korean+en 모드:
    # PaddleOCR는 "korean+en" 문자열을 단일 lang 인자로 직접 받지 않으므로
    # 한국어/영문 엔진을 각각 실행하고 결과를 합의(TTA)로 결합한다.
    if lang == "korean+en":
        engines: list[PaddleOCR] = [
            PaddleOCR(
                use_angle_cls=True,
                lang="korean",
                show_log=False,
                det_limit_side_len=3200,
                drop_score=0.3,
            ),
            PaddleOCR(
                use_angle_cls=True,
                lang="en",
                show_log=False,
                det_limit_side_len=3200,
                drop_score=0.3,
            ),
        ]
    else:
        engines = [
            PaddleOCR(
                use_angle_cls=True,
                lang=lang,
                show_log=False,
                det_limit_side_len=3200,
                drop_score=0.3,
            )
        ]

    pages: list[dict[str, Any]] = []
    merged_text_lines: list[str] = []

    for image_path in image_paths:
        page: dict[str, Any] = {"path": str(image_path.resolve()), "lines": [], "status": "ok"}
        try:
            variants = _build_variants(image_path)
            variant_lines: list[list[dict[str, Any]]] = []

            for ocr in engines:
                for _, arr in variants.items():
                    raw = ocr.ocr(arr, cls=True)
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
                            tokens.append(
                                {
                                    "text": text,
                                    "confidence": conf,
                                    "x_min": x_min,
                                    "y_center": y_center,
                                    "h": h,
                                }
                            )
                    reconstructed = _reconstruct_lines_from_boxes(tokens)
                    if reconstructed:
                        variant_lines.append(reconstructed)

            consensus = _consensus_lines(variant_lines)
            post_lines = _weak_postprocess_lines(consensus)
            if not post_lines:
                page["status"] = "empty"
            else:
                page["selected_preprocess"] = "tta_consensus_weak_postprocess"
                page["lines"] = post_lines
                for ln in post_lines:
                    merged_text_lines.append(str(ln["text"]))
        except Exception as exc:
            page["status"] = "failed"
            page["error"] = str(exc)

        pages.append(page)

    return {"images": pages, "merged_text": "\n".join(merged_text_lines)}
