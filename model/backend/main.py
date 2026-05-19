import json
import os
import uuid
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from pdf_extractor import extract
from rag_pipeline import build_vectorstore
from llm_chain import run
from database import SessionLocal, 엔진, Base
from models import Category, Document

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
UPLOAD_DIR = "data/uploads"
JSON_DIR   = "data/ocr_output"
CHROMA_DIR = "data/chroma_db"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(JSON_DIR,   exist_ok=True)
os.makedirs(CHROMA_DIR, exist_ok=True)


# ── 헬스체크 ──────────────────────────────────────────
@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ── 파일 업로드 + 파이프라인 + DB 저장 ────────────────
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):

    file_id    = str(uuid.uuid4())
    ext        = file.filename.split(".")[-1].lower()
    file_path  = f"{UPLOAD_DIR}/{file_id}.{ext}"
    json_path  = f"{JSON_DIR}/{file_id}.json"
    chroma_dir = f"{CHROMA_DIR}/{file_id}"

    with open(file_path, "wb") as f:
        f.write(await file.read())
    print(f'[업로드 완료] {file.filename} → {file_path}')

    if ext == "pdf":
        extract(file_path, json_path)
    elif ext in ("hwp", "hwpx"):
        return JSONResponse(status_code=501, content={"error": "HWP 처리는 아직 미구현입니다."})
    elif ext == "docx":
        return JSONResponse(status_code=501, content={"error": "DOCX 처리는 아직 미구현입니다."})
    elif ext in ("ppt", "pptx"):
        return JSONResponse(status_code=501, content={"error": "PPT 처리는 아직 미구현입니다."})
    else:
        return JSONResponse(status_code=400, content={"error": f".{ext} 파일은 지원하지 않습니다."})

    build_vectorstore(json_path, chroma_dir)
    result = run(json_path)

    db = SessionLocal()
    try:
        category = Category(
            main=result["main_category"],
            sub=result["sub_category"],
            extension=ext
        )
        db.add(category)
        db.flush()

        with open(json_path, encoding='utf-8') as f:
            pages = json.load(f)
        full_text = '\n\n'.join([p['content'] for p in pages])

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
    finally:
        db.close()

    return JSONResponse(content={
        "filename"      : file.filename,
        "main_category" : result["main_category"],
        "summary"       : result["summary"],
        "sub_category"  : result["sub_category"]
    })


# ── 비동기 작업 API (홍팀원 코드) ─────────────────────
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