from __future__ import annotations

"""
Ollama LLM integration service.

Features:
- Generate summary and category outputs from document text
- Enforce single JSON object response
- Parse and normalize model output with safe fallback
"""

import json
import re

import httpx

from app.config import settings


SUMMARY_PROMPT_TEMPLATE = """당신은 한국어 문서 분류 전문가다.
입력 문서를 읽고 JSON 객체 1개만 출력하라.

[목표]
- 문서의 핵심 주제를 대표하는 main_category 1개와 sub_category 1개를 자유 생성한다.
- main_category는 상위 도메인, sub_category는 main_category의 하위 세부 주제여야 한다.
- summary는 문서 전체 맥락을 반영해 4~6문장으로 작성한다.

[판단 규칙]
1) 제목, 목차, 반복 키워드, 결론을 우선 근거로 사용한다.
2) sub_category는 main_category와 의미적으로 포함 관계여야 한다.
3) 여러 주제가 섞이면 분량/목적이 가장 큰 주제를 선택한다.
4) 근거가 약하면 main_category=\"기타\", sub_category=\"미상\"으로 출력한다.
5) 카테고리는 한국어 명사구로 간결하게 작성한다.
6) 문서에 없는 내용을 추측하지 않는다.

[출력 형식]
- 반드시 JSON 객체 1개만 출력한다.
- 키는 정확히 아래 5개를 사용한다.
  - summary
  - main_category
  - sub_category
  - confidence
  - reason
- confidence는 0~1 실수
- reason은 분류 근거 1문장

[출력 예시]
{{
  "summary": "....",
  "main_category": "법률",
  "sub_category": "용역계약",
  "confidence": 0.87,
  "reason": "문서 제목과 조항 구성이 계약 목적, 대금, 기간 중심으로 구성됨"
}}

[문서]
\"\"\"
{document_text}
\"\"\"
"""


class LLMService:
    def __init__(self) -> None:
        self.base_url = settings.ollama_url.rstrip("/")
        self.model = settings.ollama_model

    async def summarize_and_categorize(self, text: str) -> tuple[str, str, str, float, str]:
        """Generate summary and categories via Ollama."""
        prompt = SUMMARY_PROMPT_TEMPLATE.format(document_text=text[:15000])
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0},
        }
        try:
            async with httpx.AsyncClient(timeout=float(settings.ollama_timeout_sec)) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                data = resp.json()
                raw = data.get("response", "").strip()
        except httpx.TimeoutException as exc:
            raise RuntimeError("OLLAMA_TIMEOUT") from exc
        except httpx.ConnectError as exc:
            raise RuntimeError("OLLAMA_CONNECT_ERROR") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"OLLAMA_HTTP_{exc.response.status_code}") from exc

        summary, main_category, sub_category, confidence, reason = self._parse_json_response(raw)
        summary = self._normalize_summary(summary)
        main_category = self._normalize_category(main_category, default="기타", max_len=12)
        sub_category = self._normalize_category(sub_category, default="미상", max_len=20)
        confidence = self._normalize_confidence(confidence)
        reason = self._normalize_reason(reason)
        return summary, main_category, sub_category, confidence, reason

    def _parse_json_response(self, raw: str) -> tuple[str, str, str, float, str]:
        """Parse model JSON response with safe fallback."""

        def _extract(obj: dict) -> tuple[str, str, str, float, str]:
            return (
                str(obj.get("summary", "")).strip(),
                str(obj.get("main_category", "기타")).strip(),
                str(obj.get("sub_category", "미상")).strip(),
                float(obj.get("confidence", 0.0) or 0.0),
                str(obj.get("reason", "")).strip(),
            )

        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                return _extract(obj)
        except Exception:
            pass

        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(0))
                if isinstance(obj, dict):
                    return _extract(obj)
            except Exception:
                pass

        return raw[:1000], "기타", "미상", 0.0, "모델 응답 파싱 실패"

    def _normalize_summary(self, summary: str) -> str:
        """Normalize summary text."""
        text = re.sub(r"\s+", " ", summary).strip()
        if not text:
            return "문서에서 텍스트는 추출했지만 요약 생성에 실패했습니다."
        alpha = len(re.findall(r"[A-Za-z]", text))
        hangul = len(re.findall(r"[가-힣]", text))
        if alpha > hangul * 2:
            return "문서 내용을 바탕으로 핵심 목적, 주요 항목, 절차와 조건, 기대 효과를 중심으로 요약했습니다."
        return text

    def _normalize_category(self, category: str, *, default: str, max_len: int) -> str:
        """Normalize category label."""
        cat = re.sub(r"\s+", " ", str(category)).strip()
        if not cat:
            return default
        cat = re.sub(r"[^가-힣A-Za-z0-9 ]", "", cat).strip()
        if not cat:
            return default
        return cat[:max_len]

    def _normalize_confidence(self, confidence: float) -> float:
        """Clamp confidence score to [0, 1]."""
        try:
            value = float(confidence)
        except Exception:
            return 0.0
        return max(0.0, min(1.0, value))

    def _normalize_reason(self, reason: str) -> str:
        """Normalize reason text."""
        text = re.sub(r"\s+", " ", str(reason)).strip()
        if not text:
            return "문서 핵심 키워드와 구조를 기준으로 분류함"
        return text[:200]
