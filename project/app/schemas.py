from pydantic import BaseModel


# 문서 처리 완료 응답
class ProcessResponse(BaseModel):
    filename: str
    raw_text: str
    ocr_text: str
    merged_text: str
    summary: str
    # 하위 호환용 (기존 프론트에서 사용)
    category: str
    # 신규 분류 필드
    main_category: str = "기타"
    sub_category: str = "미상"
    confidence: float = 0.0
    category_reason: str = ""


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


# 처리 이력 조회 응답 스키마
# - 사이드바 이력 목록 + 우측 상세 카드 표시용
# - PostgreSQL 조회 결과를 프론트에서 바로 사용하도록 정규화한 형태
class HistoryItemResponse(BaseModel):
    id: int
    filename: str
    processed_at: str
    main_category: str = "기타"
    sub_category: str = "미상"
    summary: str = ""
    status: str = "completed"
    progress: int = 100
