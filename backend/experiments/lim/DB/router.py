# router.py
# FastAPI 엔드포인트 정의 파일
# 프론트 or 파이프라인에서 HTTP 요청이 오면 여기서 받아서 DB에 넣거나 꺼내줘요

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from database import get_db, 엔진, Base
from models import Category, Document, Job

app = FastAPI()

# 서버 시작할 때 테이블이 없으면 자동으로 생성
Base.metadata.create_all(bind=엔진)


# ────────────────────────────────────────────────
# 요청/응답 형식 정의 (Pydantic 스키마)
# 클라이언트가 보내는 데이터 형식을 미리 정해두는 것
# ────────────────────────────────────────────────

class 문서저장요청(BaseModel):
    """파이프라인이 처리 완료 후 보내는 데이터"""
    file_name:    str
    file_type:    str
    file_size:    Optional[str] = None
    cat_id:       int            # 어떤 카테고리인지
    content_full: Optional[str] = None   # 전체 OCR 텍스트
    content_sum:  Optional[str] = None   # 요약문


class 문서응답(BaseModel):
    """DB에서 꺼낸 문서 정보를 클라이언트에게 돌려줄 형식"""
    doc_id:      int
    file_name:   str
    file_type:   str
    content_sum: Optional[str]
    saved_time:  Optional[datetime]

    class Config:
        from_attributes = True  # SQLAlchemy 객체 → Pydantic 자동 변환


class 작업시작요청(BaseModel):
    doc_id: Optional[int] = None  # 어떤 문서 작업인지


class 작업응답(BaseModel):
    job_id:    int
    doc_id:    Optional[int]
    status:    Optional[bool]
    job_start: Optional[datetime]

    class Config:
        from_attributes = True


# ────────────────────────────────────────────────
# Document 관련 API
# ────────────────────────────────────────────────

@app.post("/documents", response_model=문서응답)
def 문서저장(요청: 문서저장요청, db: Session = Depends(get_db)):
    """
    파이프라인 최종 결과 저장
    OCR 텍스트 + 요약 + 분류 결과를 Document 테이블에 저장해요
    """
    새문서 = Document(**요청.model_dump())
    db.add(새문서)
    db.commit()
    db.refresh(새문서)
    return 새문서


@app.get("/documents", response_model=list[문서응답])
def 문서전체조회(db: Session = Depends(get_db)):
    """
    저장된 문서 전체 목록 반환
    visible=False (삭제된 문서)는 제외하고 보여줘요
    """
    return db.query(Document).filter(Document.visible == True).all()


@app.get("/documents/{문서번호}", response_model=문서응답)
def 문서단건조회(문서번호: int, db: Session = Depends(get_db)):
    """문서 번호로 특정 문서 하나만 조회"""
    문서 = db.query(Document).filter(Document.doc_id == 문서번호).first()
    if not 문서:
        raise HTTPException(status_code=404, detail="해당 문서를 찾을 수 없어요.")
    return 문서


# ────────────────────────────────────────────────
# Job 관련 API
# ────────────────────────────────────────────────

@app.post("/jobs", response_model=작업응답)
def 작업시작(요청: 작업시작요청, db: Session = Depends(get_db)):
    """
    파이프라인 작업 시작할 때 호출
    시작 시간을 기록하고 status=False(진행중)로 등록해요
    """
    새작업 = Job(
        doc_id=요청.doc_id,
        job_start=datetime.now(),
        status=False
    )
    db.add(새작업)
    db.commit()
    db.refresh(새작업)
    return 새작업


@app.patch("/jobs/{작업번호}/done", response_model=작업응답)
def 작업완료(작업번호: int, doc_id: int, db: Session = Depends(get_db)):
    """
    파이프라인 작업 완료할 때 호출
    완료 시간을 기록하고 status=True(완료)로 업데이트해요
    """
    작업 = db.query(Job).filter(Job.job_id == 작업번호).first()
    if not 작업:
        raise HTTPException(status_code=404, detail="해당 작업을 찾을 수 없어요.")

    작업.status     = True
    작업.job_finish = datetime.now()
    작업.doc_id     = doc_id
    db.commit()
    db.refresh(작업)
    return 작업