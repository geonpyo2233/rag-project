from __future__ import annotations

"""
문서 처리 파이프라인 서비스.

역할:
1) 업로드 파일 저장
2) direct text 추출
3) 객체 이미지 추출 + OCR
4) LLM 요약/분류
5) ChromaDB 저장
6) 진행 상태(job) 관리
"""

import asyncio
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from app.config import settings
from app.schemas import JobStatusResponse, ProcessResponse
from app.services.chroma_service import ChromaService
from app.services.file_parser import (
    build_merged_text_in_order,
    clean_work_dir,
    extract_direct_text,
    extract_embedded_images_with_hwp_extract,
    save_upload,
)
from app.services.llm_service import LLMService
from app.services.ocr_service import OCRService


class PipelineService:
    def __init__(self) -> None:
        self.logger = logging.getLogger("pipeline")
        self.ocr_service = OCRService()
        self.llm_service = LLMService()
        self.chroma_service = ChromaService()
        self.jobs: dict[str, JobStatusResponse] = {}

    def start_job(self, filename: str, file_bytes: bytes) -> str:
        """비동기 작업을 시작하고 job_id를 반환한다."""
        job_id = str(uuid4())
        self.jobs[job_id] = JobStatusResponse(
            job_id=job_id,
            status="queued",
            progress=0,
            stage="queued",
            message="작업 대기 중",
            result=None,
        )
        asyncio.create_task(self._run_job(job_id, filename, file_bytes))
        return job_id

    def get_job(self, job_id: str) -> JobStatusResponse:
        """현재 작업 상태를 조회한다."""
        job = self.jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="존재하지 않는 job_id 입니다.")
        return job

    def _update_job(self, job_id: str, *, status: str, progress: int, stage: str, message: str) -> None:
        """메모리 상태와 터미널 로그를 함께 업데이트한다."""
        job = self.jobs[job_id]
        job.status = status
        job.progress = progress
        job.stage = stage
        job.message = message
        self.logger.info("[JOB %s] %s%% %s - %s", job_id, progress, stage, message)

    async def _run_job(self, job_id: str, filename: str, file_bytes: bytes) -> None:
        """실제 파이프라인 본문."""
        ext = Path(filename).suffix.lower()
        if ext not in settings.allowed_ext_set:
            self._update_job(
                job_id,
                status="failed",
                progress=100,
                stage="failed",
                message="hwp, hwpx, pdf, docx, ppt, pptx 파일만 업로드 가능합니다.",
            )
            return

        upload_dir = Path(settings.upload_dir)
        work_dir = Path(settings.work_dir) / job_id
        saved_path = upload_dir / f"{job_id}{ext}"

        try:
            self._update_job(job_id, status="running", progress=5, stage="upload", message="파일 저장 중")
            save_upload(file_bytes, saved_path)

            self._update_job(job_id, status="running", progress=20, stage="extract_text", message="문서 텍스트 추출 중")
            raw_text = extract_direct_text(saved_path)

            self._update_job(job_id, status="running", progress=40, stage="extract_images", message="이미지/객체 추출 중")
            image_dir = work_dir / "images"
            image_paths = extract_embedded_images_with_hwp_extract(saved_path, image_dir)
            self.logger.info("[JOB %s] extracted image files: %s", job_id, len(image_paths))

            self._update_job(job_id, status="running", progress=55, stage="ocr", message="OCR 처리 중")
            ocr_by_image = self.ocr_service.ocr_images_map(image_paths) if image_paths else {}
            ocr_text = "\n\n".join(t for t in ocr_by_image.values() if t).strip()
            self.logger.info("[JOB %s] ocr text length: %s", job_id, len(ocr_text))

            merged_text = build_merged_text_in_order(
                source_path=saved_path,
                raw_text=raw_text,
                image_paths=image_paths,
                ocr_by_image=ocr_by_image,
            )
            if not merged_text:
                self._update_job(
                    job_id,
                    status="failed",
                    progress=100,
                    stage="failed",
                    message="텍스트를 추출하지 못했습니다.",
                )
                return

            self._update_job(job_id, status="running", progress=70, stage="llm", message="요약/분류 생성 중")
            try:
                summary, category = await self.llm_service.summarize_and_categorize(merged_text)
            except RuntimeError as exc:
                code = str(exc)
                if code == "OLLAMA_TIMEOUT":
                    self._update_job(job_id, status="failed", progress=100, stage="failed", message="LLM 응답 시간 초과")
                    return
                if code == "OLLAMA_CONNECT_ERROR":
                    self._update_job(job_id, status="failed", progress=100, stage="failed", message="Ollama 연결 실패")
                    return
                self._update_job(job_id, status="failed", progress=100, stage="failed", message=f"Ollama 오류: {code}")
                return

            self._update_job(job_id, status="running", progress=85, stage="db_raw", message="원문 DB 저장 중")
            source_id = self.chroma_service.save_raw(filename, raw_text, ocr_text, merged_text)

            self._update_job(job_id, status="running", progress=95, stage="db_summary", message="요약/분류 DB 저장 중")
            self.chroma_service.save_summary(source_id, filename, summary, category)

            result = ProcessResponse(
                filename=filename,
                raw_text=raw_text,
                ocr_text=ocr_text,
                merged_text=merged_text,
                summary=summary,
                category=category,
            )
            self.jobs[job_id].result = result
            self._update_job(job_id, status="completed", progress=100, stage="completed", message="처리 완료")
        except Exception as exc:
            self.logger.exception("[JOB %s] unexpected error", job_id)
            self._update_job(job_id, status="failed", progress=100, stage="failed", message=f"처리 실패: {exc}")
        finally:
            clean_work_dir(work_dir)
