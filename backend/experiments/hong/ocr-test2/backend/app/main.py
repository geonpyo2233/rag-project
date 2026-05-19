from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.schemas import (
    JobStatusResponse,
    ProcessStartResponse,
    # SearchHit,
    # SearchRequest,
    # SearchResponse,
)
from app.services.pipeline import PipelineService

# FastAPI 앱 초기화
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = PipelineService()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


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


# 검색 기능은 현재 미사용으로 주석 처리
# @app.post("/api/search", response_model=SearchResponse)
# def search_documents(req: SearchRequest) -> SearchResponse:
#     """저장된 원문 벡터 컬렉션에서 유사 문서를 검색한다."""
#     result = pipeline.chroma_service.search_raw(query=req.query, limit=req.limit)
#
#     ids = result.get("ids", [[]])[0]
#     docs = result.get("documents", [[]])[0]
#     metas = result.get("metadatas", [[]])[0]
#     dists = result.get("distances", [[]])[0] if result.get("distances") else []
#
#     hits: list[SearchHit] = []
#     for i, doc_id in enumerate(ids):
#         hits.append(
#             SearchHit(
#                 id=doc_id,
#                 document=docs[i] if i < len(docs) else "",
#                 metadata=metas[i] if i < len(metas) else {},
#                 distance=dists[i] if i < len(dists) else None,
#             )
#         )
#
#     return SearchResponse(query=req.query, hits=hits)
