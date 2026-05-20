# ==============================
# app/services/pipeline.py
# ==============================
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException

from app.config import settings
from app.schemas import JobStatusResponse, ProcessResponse
from database import SessionLocal
from extractors.docx_ext.docx_extractor import docx_extractor
from extractors.hwp_ext.hwp_extractor import hwp_extractor
from extractors.pdf_ext.pdf_extractor import pdf_extractor, extract
from extractors.ppt_ext.ppt_extractor import ppt_extractor
from llm_chain import run as llm_run
from models import Category, Document
from rag_pipeline import build_vectorstore


class PipelineService:
    """
    파이프라인 전체 흐름 관리 서비스.

    Flow:
      1) 파일 저장
      2) 확장자별 extractor 실행 → 텍스트 추출 + JSON 저장
      3) RAG (청킹 → 임베딩 → Chroma 저장)
      4) LLM (요약 + 카테고리 분류)
      5) PostgreSQL DB 저장
      6) 비동기 job 상태 추적
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("pipeline")
        self.jobs: dict[str, JobStatusResponse] = {}

        # 필요한 폴더 자동 생성
        for d in [settings.upload_dir, settings.work_dir, settings.chroma_dir,
                  "./data/ocr_output"]:
            Path(d).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_job(self, filename: str, file_bytes: bytes) -> str:
        """비동기 처리 작업을 시작하고 job_id를 반환한다."""
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
        """job_id로 현재 작업 상태를 반환한다."""
        job = self.jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="존재하지 않는 job_id 입니다.")
        return job

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update(self, job_id: str, *, status: str, progress: int,
                stage: str, message: str) -> None:
        job = self.jobs[job_id]
        job.status   = status
        job.progress = progress
        job.stage    = stage
        job.message  = message
        self.logger.info("[JOB %s] %s%% %s – %s", job_id, progress, stage, message)

    # ------------------------------------------------------------------
    # Pipeline body
    # ------------------------------------------------------------------

    async def _run_job(self, job_id: str, filename: str, file_bytes: bytes) -> None:
        ext = Path(filename).suffix.lower().lstrip(".")

        if f".{ext}" not in settings.allowed_ext_set:
            self._update(job_id, status="failed", progress=100,
                         stage="failed",
                         message="hwp, hwpx, pdf, docx, ppt, pptx 파일만 업로드 가능합니다.")
            return

        upload_dir = Path(settings.upload_dir)
        json_dir   = Path("./data/ocr_output")
        chroma_dir = Path(settings.chroma_dir) / job_id
        saved_path = upload_dir / f"{job_id}.{ext}"
        json_path  = json_dir  / f"{job_id}.json"

        try:
            # ── STEP 1 : 파일 저장 ──────────────────────────────────────
            self._update(job_id, status="running", progress=5,
                         stage="upload", message="파일 저장 중")
            saved_path.write_bytes(file_bytes)
            self.logger.info("[JOB %s] 파일 저장 완료: %s", job_id, saved_path)

            # ── STEP 2 : 확장자별 텍스트 추출 ───────────────────────────
            self._update(job_id, status="running", progress=20,
                         stage="extract", message="문서 텍스트 추출 중")

            result_text = await asyncio.get_event_loop().run_in_executor(
                None, self._extract, saved_path, json_path, ext
            )

            if not result_text:
                self._update(job_id, status="failed", progress=100,
                             stage="failed", message="텍스트를 추출하지 못했습니다.")
                return

            # ── STEP 3 : RAG (청킹 → 임베딩 → Chroma) ──────────────────
            self._update(job_id, status="running", progress=55,
                         stage="rag", message="벡터 DB 저장 중")
            await asyncio.get_event_loop().run_in_executor(
                None, build_vectorstore, str(json_path), str(chroma_dir)
            )

            # ── STEP 4 : LLM 요약 + 카테고리 분류 ──────────────────────
            self._update(job_id, status="running", progress=70,
                         stage="llm", message="요약/분류 생성 중")
            llm_result = await asyncio.get_event_loop().run_in_executor(
                None, llm_run, str(json_path)
            )
            main_category = llm_result.get("main_category", "기타")
            sub_category  = llm_result.get("sub_category",  "미상")
            summary       = llm_result.get("summary",       "")

            # ── STEP 5 : PostgreSQL DB 저장 ─────────────────────────────
            self._update(job_id, status="running", progress=90,
                         stage="db", message="DB 저장 중")
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._save_to_db,
                filename, ext, str(saved_path),
                result_text, summary, main_category, sub_category,
            )

            # ── 완료 ────────────────────────────────────────────────────
            result = ProcessResponse(
                filename=filename,
                raw_text=result_text,
                ocr_text="",
                merged_text=result_text,
                summary=summary,
                category=main_category,
                main_category=main_category,
                sub_category=sub_category,
            )
            self.jobs[job_id].result = result
            self._update(job_id, status="completed", progress=100,
                         stage="completed", message="처리 완료")

        except Exception as exc:
            self.logger.exception("[JOB %s] 예상치 못한 오류", job_id)
            self._update(job_id, status="failed", progress=100,
                         stage="failed", message=f"처리 실패: {exc}")

    # ------------------------------------------------------------------
    # Extractor 라우터  (document_pipeline.py 흡수)
    # ------------------------------------------------------------------

    def _extract(self, saved_path: Path, json_path: Path, ext: str) -> str:
        """
        확장자에 맞는 extractor를 호출하고 공통 JSON + 텍스트를 반환한다.
        PDF는 pdfplumber/OCR 결과를 json_path에 저장한다.
        나머지 포맷은 extractor 결과 텍스트를 json_path에 통일된 형식으로 저장한다.
        """
        if ext == "pdf":
            # pdf_extractor는 json_path에 직접 저장하고 텍스트를 반환한다
            result = pdf_extractor(saved_path)
            # json_path 위치로 복사 (pdf_extractor는 OUTPUT_DIR에 저장함)
            if result.get("json_path") and Path(result["json_path"]).exists():
                shutil.copy(result["json_path"], json_path)
            return result.get("text", "")

        elif ext == "docx":
            result = docx_extractor(saved_path)
            text = result.get("text", "")

        elif ext in ("ppt", "pptx"):
            slide_texts = ppt_extractor(saved_path)
            text = "\n\n".join(slide_texts) if isinstance(slide_texts, list) else ""

        elif ext in ("hwp", "hwpx"):
            result = hwp_extractor(saved_path)
            text = result.get("text", "")

        else:
            raise ValueError(f"지원하지 않는 확장자: .{ext}")

        # PDF 이외 포맷은 llm_chain/rag_pipeline이 읽을 수 있도록
        # 동일한 JSON 구조로 저장한다
        pages = [{"page": 1, "method": ext, "content": text}]
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            __import__("json").dumps(pages, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return text

    # ------------------------------------------------------------------
    # DB 저장  (database.py + models.py 연결)
    # ------------------------------------------------------------------

    def _save_to_db(self, filename: str, ext: str, file_path: str,
                    full_text: str, summary: str,
                    main_category: str, sub_category: str) -> None:
        db = SessionLocal()
        try:
            category = Category(
                main=main_category,
                sub=sub_category,
                extension=ext,
            )
            db.add(category)
            db.flush()  # cat_id 먼저 확보

            document = Document(
                file_name=filename,
                file_type=ext,
                file_size=str(os.path.getsize(file_path)),
                cat_id=category.cat_id,
                content_full=full_text,
                content_sum=summary,
            )
            db.add(document)
            db.commit()
            self.logger.info("DB 저장 완료: %s", filename)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
