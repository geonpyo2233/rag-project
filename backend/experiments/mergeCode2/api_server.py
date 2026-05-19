from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipelines.document_pipeline import run_document_pipeline
from utils.file_utils import sanitize_filename, unique_path

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class ProcessResponse(BaseModel):
    filename: str
    summary: str
    category: str


class ProcessStartResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    stage: str
    message: str = ""
    result: ProcessResponse | None = None


@dataclass
class JobRecord:
    job_id: str
    status: str = "queued"
    progress: int = 0
    stage: str = "queued"
    message: str = ""
    result: ProcessResponse | None = None


app = FastAPI(title="mergeCode2 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=2)
jobs: dict[str, JobRecord] = {}


def _summarize(text: str) -> str:
    compact = " ".join((text or "").split())
    if not compact:
        return "요약 가능한 텍스트를 추출하지 못했습니다."
    return compact[:700]


def _category_from_file(file_name: str) -> str:
    ext = Path(file_name).suffix.lower()
    mapping = {
        ".hwp": "한글문서",
        ".hwpx": "한글문서",
        ".docx": "워드문서",
        ".pdf": "PDF",
        ".ppt": "프레젠테이션",
        ".pptx": "프레젠테이션",
    }
    return mapping.get(ext, "기타")


def _process_job(job: JobRecord, stored_path: Path) -> None:
    try:
        job.status = "running"
        job.progress = 20
        job.stage = "extract"
        result = run_document_pipeline(stored_path)

        extracted_text = ""
        if isinstance(result, dict):
            extracted_text = str(result.get("text") or "")

        job.progress = 85
        job.stage = "postprocess"
        summary = _summarize(extracted_text)
        category = _category_from_file(stored_path.name)

        job.result = ProcessResponse(
            filename=stored_path.name,
            summary=summary,
            category=category,
        )
        job.status = "completed"
        job.progress = 100
        job.stage = "completed"
        job.message = f"완료: {datetime.now().isoformat(timespec='seconds')}"
    except Exception as exc:
        job.status = "failed"
        job.progress = 100
        job.stage = "failed"
        job.message = str(exc)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/process/start", response_model=ProcessStartResponse)
async def start_process(file: UploadFile = File(...)) -> ProcessStartResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 없습니다.")

    file_name = sanitize_filename(file.filename)
    extension = Path(file_name).suffix.lower()
    if extension not in {".hwp", ".hwpx", ".pdf", ".docx", ".ppt", ".pptx"}:
        raise HTTPException(status_code=400, detail="지원하지 않는 파일 형식입니다.")

    stored_path = unique_path(UPLOAD_DIR / file_name)
    file_bytes = await file.read()
    stored_path.write_bytes(file_bytes)

    job_id = str(uuid.uuid4())
    record = JobRecord(job_id=job_id)
    jobs[job_id] = record

    executor.submit(_process_job, record, stored_path)
    return ProcessStartResponse(job_id=job_id)


@app.get("/api/process/{job_id}", response_model=JobStatusResponse)
def get_process_status(job_id: str) -> JobStatusResponse:
    record = jobs.get(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="job_id를 찾을 수 없습니다.")

    return JobStatusResponse(
        job_id=record.job_id,
        status=record.status,
        progress=record.progress,
        stage=record.stage,
        message=record.message,
        result=record.result,
    )
