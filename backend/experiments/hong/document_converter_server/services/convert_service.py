from __future__ import annotations

from pathlib import Path

from services.routing_service import process_document_with_routing
from utils.logger import get_logger


logger = get_logger(__name__)


def convert_document(
    source_path: Path,
    render_scale: float,
) -> dict:
    """Keep the existing service entrypoint while using the hybrid routing pipeline."""
    source_path = source_path.resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Uploaded file not found: {source_path}")

    logger.info("Dispatching conversion through routing pipeline: %s", source_path)
    result = process_document_with_routing(source_path, render_scale=render_scale)
    result["final_text"] = result.get("extracted_text", "")
    result["summary"] = ""

    # Ollama 후처리는 현재 임시 비활성화 상태입니다.
    # 변환 결과는 그대로 유지합니다(직접 텍스트 추출 + 객체 이미지 전용 OCR 정책).
    #
    # 나중에 다시 활성화하려면 아래 블록을 복원하고 import를 다시 추가하세요.
    #   from config import OLLAMA_ENABLED
    #   from services.llm_service import build_final_text_and_summary
    #
    # if OLLAMA_ENABLED:
    #     try:
    #         llm_output = build_final_text_and_summary(result.get("extracted_text", ""))
    #         result["llm_status"] = "completed"
    #         result["llm_result"] = llm_output
    #         result["final_text"] = llm_output.get("final_text", "") or result["final_text"]
    #         result["summary"] = llm_output.get("summary", "")
    #     except Exception as exc:
    #         logger.warning("Ollama post-processing failed: %s", exc)
    #         result["llm_status"] = "failed"
    #         result["llm_error"] = str(exc)
    # else:
    #     result["llm_status"] = "disabled"
    #     result["llm_error"] = "OLLAMA_ENABLED is false. Set OLLAMA_ENABLED=true to enable LLM post-processing."

    result["llm_status"] = "disabled"
    result["llm_error"] = "Ollama post-processing is temporarily disabled."

    return result
