import json
import os
import uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from extractors.pdf_ext.pdf_extractor import pdf_extractor
from extractors.hwp_ext.hwp_extractor import hwp_extractor
from extractors.docx_ext.docx_extractor import docx_extractor
from extractors.ppt_ext.ppt_extractor import ppt_extractor
from rag_pipeline import build_vectorstore
from llm_chain import run
from database import SessionLocal, 엔진, Base
from models import Category, Document
from check_file import check_input_files

from app.config import settings
from app.schemas import JobStatusResponse, ProcessStartResponse
from app.services.pipeline import PipelineService

# FastAPI 앱 초기화
app = FastAPI(title=settings.app_name)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 테이블 자동 생성
Base.metadata.create_all(bind=엔진)

# 파이프라인 서비스
pipeline = PipelineService()

# 폴더 설정
BASE_DIR   = Path(__file__).resolve().parent
DATA_DIR   = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "data/uploads"
JSON_DIR   = BASE_DIR / "data/ocr_output"
CHROMA_DIR = BASE_DIR / "data/chroma_db"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
JSON_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)


# ── 헬스체크 ──────────────────────────────────────────
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ── 파일 업로드 + 파이프라인 + DB 저장 ────────────────
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):

    file_id    = str(uuid.uuid4())
    ext        = file.filename.split(".")[-1].lower()
    file_path  = UPLOAD_DIR / f"{file_id}.{ext}"
    json_path  = str(JSON_DIR / f"{file_id}.json")
    chroma_dir = str(CHROMA_DIR / file_id)

    # 파일 저장
    with open(file_path, "wb") as f:
        f.write(await file.read())
    print(f'[업로드 완료] {file.filename} → {file_path}')

    # 확장자별 추출 (경로 기반)
    if ext == "pdf":
        extract_result = pdf_extractor(file_path)
    elif ext in ("hwp", "hwpx"):
        extract_result = hwp_extractor(file_path)
    elif ext == "docx":
        extract_result = docx_extractor(file_path)
    elif ext in ("ppt", "pptx"):
        extract_result = ppt_extractor(file_path)
    else:
        return JSONResponse(status_code=400, content={"error": f".{ext} 파일은 지원하지 않습니다."})

    # RAG + LLM 실행
    build_vectorstore(json_path, chroma_dir)
    result = run(json_path)

    # DB 저장
    db = SessionLocal()
    try:
        category = Category(
            main=result["main_category"],
            sub=result["sub_category"],
            extension=ext
        )
        db.add(category)
        db.flush()

        # 추출된 텍스트 가져오기
        full_text = extract_result.get("text", "") if extract_result else ""

        document = Document(
            file_name=file.filename,
            file_type=ext,
            file_size=str(os.path.getsize(file_path)),
            cat_id=category.cat_id,
            content_full=full_text,
            content_sum=result["summary"]
        )
        db.add(document)
        db.commit()
        print("[DB 저장 완료]")
    except Exception as e:
        db.rollback()
        print(f"[DB 저장 실패] {e}")
    finally:
        db.close()

    return JSONResponse(content={
        "filename"      : file.filename,
        "main_category" : result["main_category"],
        "summary"       : result["summary"],
        "sub_category"  : result["sub_category"]
    })


# ── 배치 처리 API (data 폴더 전체 처리) ───────────────
@app.post("/batch")
def batch_process():
    """data 폴더 안의 파일들을 일괄 처리"""
    print("===== BATCH PIPELINE START =====")
    selected_files = check_input_files(DATA_DIR)

    results = []
    for file_path in selected_files:
        ext = file_path.suffix.lower().lstrip(".")
        if ext == "pdf":
            pdf_extractor(file_path)
        elif ext in ("hwp", "hwpx"):
            hwp_extractor(file_path)
        elif ext == "docx":
            docx_extractor(file_path)
        elif ext in ("ppt", "pptx"):
            ppt_extractor(file_path)
        results.append(file_path.name)

    return JSONResponse(content={
        "message": f"{len(selected_files)}개 파일 처리 완료",
        "files": results
    })


# ── 비동기 작업 API ────────────────────────────────────
@app.post("/api/process/start", response_model=ProcessStartResponse)
async def start_process(file: UploadFile = File(...)) -> ProcessStartResponse:
    """문서 처리 비동기 작업을 시작하고 job_id를 반환한다."""
    filename = file.filename or "unknown"
    file_bytes = await file.read()
    job_id = pipeline.start_job(filename=filename, file_bytes=file_bytes)
    return ProcessStartResponse(job_id=job_id)


@app.get("/api/process/{job_id}", response_model=JobStatusResponse)
def get_process_status(job_id: str) -> JobStatusResponse:
    """job_id 기준 처리 상태를 조회한다."""
    return pipeline.get_job(job_id)