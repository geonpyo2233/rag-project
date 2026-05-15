from pydantic import BaseModel


# 문서 처리 완료 응답
class ProcessResponse(BaseModel):
    filename: str
    raw_text: str
    ocr_text: str
    merged_text: str
    summary: str
    category: str


# 검색 요청/응답
class SearchRequest(BaseModel):
    query: str
    limit: int = 5


class SearchHit(BaseModel):
    id: str
    document: str
    distance: float | None = None
    metadata: dict


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]


# 비동기 처리 상태 응답
class ProcessStartResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    stage: str
    message: str = ""
    result: ProcessResponse | None = None
