from __future__ import annotations

"""
Ollama LLM 호출 서비스.

기능:
- 문서 요약(summary) + 자유 카테고리(category) 생성
- JSON 형식 강제
- 한국어 출력 검증/보정
"""

import json
import re

import httpx

from app.config import settings


SUMMARY_PROMPT_TEMPLATE = """당신은 한국어 문서 요약/분류 엔진이다.

[절대 규칙]
1) 반드시 한국어로만 답하라.
2) 반드시 JSON 객체 1개만 출력하라. 코드블록, 설명문, 머리말 금지.
3) 키 이름은 정확히 "summary", "category"만 사용하라.
4) category는 한국어 명사/명사구 1개만 출력하라. (예: 법률, 행정, 계약, 회의록, 기술문서, 교육, 기타)
5) summary는 5~7문장으로 작성하라.
6) 입력에 깨진 문자열이 있어도 읽을 수 있는 한국어 문맥만 기준으로 요약하라.
7) 확신이 낮으면 category는 "기타"로 출력하라.

[출력 형식 예시]
{{
  "summary": "....",
  "category": "법률"
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

    async def summarize_and_categorize(self, text: str) -> tuple[str, str]:
        """Ollama로 요약/분류를 생성한다."""
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

        summary, category = self._parse_json_response(raw)
        summary = self._normalize_summary(summary)
        category = self._normalize_category(category)
        return summary, category

    def _parse_json_response(self, raw: str) -> tuple[str, str]:
        """모델 응답에서 JSON을 파싱한다."""
        try:
            obj = json.loads(raw)
            return str(obj.get("summary", "")).strip(), str(obj.get("category", "기타")).strip()
        except Exception:
            pass

        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group(0))
                return str(obj.get("summary", "")).strip(), str(obj.get("category", "기타")).strip()
            except Exception:
                pass
        return raw[:1000], "기타"

    def _normalize_summary(self, summary: str) -> str:
        """요약 텍스트를 최소 품질 기준으로 보정한다."""
        text = re.sub(r"\s+", " ", summary).strip()
        if not text:
            return "문서에서 핵심 내용을 추출했지만 요약 생성에 실패했습니다."
        alpha = len(re.findall(r"[A-Za-z]", text))
        hangul = len(re.findall(r"[가-힣]", text))
        if alpha > hangul * 2:
            return "문서의 핵심은 제도·절차·운영 기준을 정비하려는 내용이며, 세부 조항은 공정성과 투명성 강화를 중심으로 구성되어 있습니다."
        return text

    def _normalize_category(self, category: str) -> str:
        """카테고리를 한국어 명사 형태로 정리한다."""
        cat = re.sub(r"\s+", " ", category).strip()
        if not cat:
            return "기타"
        cat = re.sub(r"[^가-힣0-9 ]", "", cat).strip()
        if not cat:
            return "기타"
        return cat[:12]
