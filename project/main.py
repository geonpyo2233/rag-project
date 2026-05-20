# ==============================
# main.py  –  FastAPI 서버 진입점
# ==============================
import asyncio
import json
import logging
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.schemas import JobStatusResponse, ProcessStartResponse, ProcessResponse
from database import Base, 엔진, SessionLocal
from models import Category, Document, Job
from document_pipeline import run_document_pipeline
from rag_pipeline import build_vectorstore
from llm_chain import run as llm_run
from datetime import datetime

# ── 로깅 ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("main")

# ── DB 테이블 자동 생성 ──────────────────────────────────────────────────
Base.metadata.create_all(bind=엔진)

# ── 폴더 자동 생성 ───────────────────────────────────────────────────────
UPLOAD_DIR = Path(settings.upload_dir)
JSON_DIR   = Path(settings.ocr_output_dir)
CHROMA_DIR = Path(settings.chroma_dir)

for _d in [UPLOAD_DIR, JSON_DIR, CHROMA_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ── FastAPI 앱 ───────────────────────────────────────────────────────────
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Job 상태 저장소 (in-memory) ──────────────────────────────────────────
jobs: dict[str, JobStatusResponse] = {}


def _update_job(job_id: str, *, status: str, progress: int,
                stage: str, message: str) -> None:
    job = jobs[job_id]
    job.status   = status
    job.progress = progress
    job.stage    = stage
    job.message  = message
    logger.info("[JOB %s] %s%% %s – %s", job_id, progress, stage, message)


async def _run_pipeline(job_id: str, filename: str, file_bytes: bytes) -> None:
    """
    전체 파이프라인 비동기 실행.

    1) 파일 저장
    2) document_pipeline → 각 extractor (퍼널)
    3) rag_pipeline      → 청킹 + 임베딩 + Chroma
    4) llm_chain         → 요약 + 카테고리 분류
    5) DB 저장           → Category + Document
    """
    job_start_time = datetime.now()
    ext = Path(filename).suffix.lower().lstrip(".")
    saved_path = UPLOAD_DIR / f"{job_id}.{ext}"
    json_path  = JSON_DIR   / f"{job_id}.json"
    chroma_dir = str(CHROMA_DIR / job_id)

    try:
        # ── STEP 1 : 파일 저장 ─────────────────────────────────────────
        _update_job(job_id, status="running", progress=5,
                    stage="upload", message="파일 저장 중")
        saved_path.write_bytes(file_bytes)

        # ── STEP 2 : 확장자별 추출 (퍼널) ──────────────────────────────
        _update_job(job_id, status="running", progress=20,
                    stage="extract", message="문서 텍스트 추출 중")

        loop = asyncio.get_event_loop()
        extract_result = await loop.run_in_executor(
            None, run_document_pipeline, saved_path
        )

        # extractor 결과에서 json_path 확보
        # pdf_extractor는 json_path를 직접 반환, 나머지는 text를 JSON으로 변환
        if extract_result and extract_result.get("json_path"):
            json_path = Path(extract_result["json_path"])
        else:
            # pdf 이외 포맷: text를 rag_pipeline이 읽을 수 있는 JSON으로 저장
            text = extract_result.get("text", "") if extract_result else ""
            if not text:
                _update_job(job_id, status="failed", progress=100,
                            stage="failed", message="텍스트를 추출하지 못했습니다.")
                return
            pages = [{"page": 1, "method": ext, "content": text}]
            json_path.write_text(
                json.dumps(pages, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

        # ── STEP 3 : RAG (청킹 → 임베딩 → Chroma) ─────────────────────
        _update_job(job_id, status="running", progress=55,
                    stage="rag", message="벡터 DB 저장 중")
        await loop.run_in_executor(
            None, build_vectorstore, str(json_path), chroma_dir
        )

        # ── STEP 4 : LLM 요약 + 카테고리 분류 ─────────────────────────
        _update_job(job_id, status="running", progress=70,
                    stage="llm", message="요약/분류 생성 중")
        llm_result = await loop.run_in_executor(
            None, llm_run, str(json_path)
        )
        main_category = llm_result.get("main_category", "기타")
        sub_category  = llm_result.get("sub_category",  "미상")
        summary       = llm_result.get("summary",       "")

        # ── STEP 5 : PostgreSQL DB 저장 ────────────────────────────────
        _update_job(job_id, status="running", progress=90,
                    stage="db", message="DB 저장 중")

        with open(json_path, encoding="utf-8") as f:
            pages = json.load(f)
        full_text = "\n\n".join(p["content"] for p in pages)

        db = SessionLocal()
        try:
            category = Category(
                main=main_category,
                sub=sub_category,
                extension=ext,
            )
            db.add(category)
            db.flush()

            document = Document(
                file_name=filename,
                file_type=ext,
                file_size=str(os.path.getsize(saved_path)),
                cat_id=category.cat_id,
                content_full=full_text,
                content_sum=summary,
            )
            db.add(document)
            db.flush()
            

            
            job_record = Job(
                job_start=job_start_time,
                job_finish=datetime.now(),
                doc_id=document.doc_id,
                status=True  # 완료
            )
            db.add(job_record)
            db.commit()
            logger.info("[JOB %s] DB 저장 완료", job_id)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        # ── 완료 ───────────────────────────────────────────────────────
        result = ProcessResponse(
            filename=filename,
            raw_text=full_text,
            ocr_text="",
            merged_text=full_text,
            summary=summary,
            category=main_category,
            main_category=main_category,
            sub_category=sub_category,
        )
        jobs[job_id].result = result
        _update_job(job_id, status="completed", progress=100,
                    stage="completed", message="처리 완료")

    except Exception as exc:
        logger.exception("[JOB %s] 예상치 못한 오류", job_id)
        _update_job(job_id, status="failed", progress=100,
                    stage="failed", message=f"처리 실패: {exc}")


# ── 엔드포인트 ───────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/process/start", response_model=ProcessStartResponse)
async def start_process(file: UploadFile = File(...)) -> ProcessStartResponse:
    """파일 업로드 → 비동기 파이프라인 시작 → job_id 반환."""
    ext = Path(file.filename or "").suffix.lower().lstrip(".")
    if f".{ext}" not in settings.allowed_ext_set:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail="hwp, hwpx, pdf, docx, ppt, pptx 파일만 업로드 가능합니다."
        )

    filename   = file.filename or "unknown"
    file_bytes = await file.read()
    job_id     = str(uuid.uuid4())

    jobs[job_id] = JobStatusResponse(
        job_id=job_id,
        status="queued",
        progress=0,
        stage="queued",
        message="작업 대기 중",
        result=None,
    )

    asyncio.create_task(_run_pipeline(job_id, filename, file_bytes))
    return ProcessStartResponse(job_id=job_id)


@app.get("/api/process/{job_id}", response_model=JobStatusResponse)
def get_process_status(job_id: str) -> JobStatusResponse:
    """job_id 기준 처리 상태 조회."""
    job = jobs.get(job_id)
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="존재하지 않는 job_id 입니다.")
    return job
