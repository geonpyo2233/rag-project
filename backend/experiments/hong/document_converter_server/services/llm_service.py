from __future__ import annotations

import json
import re
from urllib import error, request

from config import (
    OLLAMA_BASE_URL,
    OLLAMA_MAX_INPUT_CHARS,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
)


SUMMARY_PROMPT_GENERAL = (
    "반드시 한국어로만 작성하라. "
    "아래 문서를 5~8줄로 요약하라. "
    "형식은 '핵심 주제', '주요 내용', '결론' 순서로 작성하라. "
    "원문에 없는 사실을 추가하지 마라."
)

SUMMARY_PROMPT_RECEIPT = (
    "반드시 한국어로만 작성하라. "
    "아래 OCR 영수증 텍스트를 3~6줄로 요약하라. "
    "형식은 '핵심 주제', '주요 내용', '결론' 순서로 작성하라. "
    "숫자/금액/상호는 OCR 오인식 가능성이 있으므로 단정하지 말고 '추정' 또는 '원문 기준'으로 표현하라. "
    "영어/일본어/중국어 문장을 섞지 마라."
)


def normalize_final_text(text: str) -> str:
    normalized = (text or "").replace("‼", "·")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    return normalized.strip()


def _generate_with_ollama(
    text: str,
    *,
    prompt: str,
    model: str | None = None,
) -> dict[str, str]:
    source = (text or "").strip()
    if not source:
        return {"model": model or OLLAMA_MODEL, "text": ""}

    clipped = source[:OLLAMA_MAX_INPUT_CHARS]
    payload = {
        "model": model or OLLAMA_MODEL,
        "prompt": f"{prompt}\n\n[문서 본문]\n{clipped}",
        "stream": False,
    }

    req = request.Request(
        url=f"{OLLAMA_BASE_URL}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama HTTP error {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Ollama connection failed: {exc.reason}") from exc

    parsed = json.loads(body)
    generated = str(parsed.get("response") or "").strip()
    return {"model": payload["model"], "text": generated}


def _looks_like_receipt(text: str) -> bool:
    compact = re.sub(r"\s+", " ", (text or "")).lower()
    keywords = ["영수증", "receipt", "subtotal", "tax", "tip", "total", "부가세", "품목", "단가"]
    hits = sum(1 for token in keywords if token in compact)
    return hits >= 2


def _contains_non_korean_noise(text: str) -> bool:
    # Japanese kana / CJK ideographs leakage for Korean-only output.
    if re.search(r"[ぁ-んァ-ン一-龯]", text):
        return True
    return False


def _contains_english_sentence(text: str) -> bool:
    # Sentence-like English leakage, not just one token/code.
    return re.search(r"[A-Za-z]{3,}\s+[A-Za-z]{2,}", text) is not None


def _fallback_summary_for_receipt() -> str:
    return (
        "핵심 주제: OCR 기반 영수증 텍스트 정리\n\n"
        "주요 내용: 문서에는 매장 정보, 거래 시각, 품목명, 수량, 단가, 금액 관련 항목이 포함되어 있으며 "
        "일부 문자는 OCR 인식 오차가 있습니다.\n\n"
        "결론: 본 결과는 원문 보존 중심으로 정리되었고, 금액/코드 등 주요 항목은 원문 이미지와 교차 확인이 필요합니다."
    )


def _fallback_summary_general() -> str:
    return (
        "핵심 주제: 문서 핵심 내용 요약\n\n"
        "주요 내용: 원문 텍스트를 기준으로 핵심 항목을 정리했으며, OCR 또는 추출 과정에서 일부 오인식이 있을 수 있습니다.\n\n"
        "결론: 최종 확인이 필요한 고유명사/수치/코드는 원문 파일과 함께 검토하는 것이 안전합니다."
    )


def build_final_text_and_summary(
    text: str,
    *,
    model: str | None = None,
) -> dict[str, str]:
    final_text = normalize_final_text(text)
    is_receipt = _looks_like_receipt(final_text)
    summary_prompt = SUMMARY_PROMPT_RECEIPT if is_receipt else SUMMARY_PROMPT_GENERAL

    summary_output = _generate_with_ollama(
        final_text,
        prompt=summary_prompt,
        model=model,
    )
    summary_text = normalize_final_text(summary_output["text"])

    if _contains_non_korean_noise(summary_text) or _contains_english_sentence(summary_text):
        retry_prompt = summary_prompt + " 추가 지시: 한국어 문장만 사용하라."
        retry_output = _generate_with_ollama(
            final_text,
            prompt=retry_prompt,
            model=model,
        )
        if retry_output["text"]:
            summary_text = normalize_final_text(retry_output["text"])

    if _contains_non_korean_noise(summary_text) or _contains_english_sentence(summary_text):
        summary_text = _fallback_summary_for_receipt() if is_receipt else _fallback_summary_general()

    return {
        "model": summary_output["model"],
        "final_text": final_text,
        "summary": summary_text,
    }
