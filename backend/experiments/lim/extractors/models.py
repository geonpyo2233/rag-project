# models.py
# DB 테이블 구조를 Python 클래스로 정의하는 파일
# 여기 작성한 클래스 = 실제 PostgreSQL 테이블

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Category(Base):
    """
    [문서 분류 테이블]
    Ollama가 분류한 카테고리 정보를 저장해요
    예) main = "계약서", sub = "임대차계약", extension = "pdf"
    """
    __tablename__ = "category"

    cat_id    = Column(Integer,     primary_key=True, autoincrement=True)  # 분류 고유번호 (자동증가)
    main      = Column(String(100), nullable=True)   # 대분류  예: 계약서
    sub       = Column(String(100), nullable=True)   # 소분류  예: 임대차계약
    extension = Column(String(50),  nullable=True)   # 확장자  예: pdf

    # Category 1개 → Document 여러 개 연결
    문서목록 = relationship("Document", back_populates="분류")


class Document(Base):
    """
    [문서 정보 테이블]
    업로드된 파일 정보 + OCR 텍스트 + 요약 결과를 저장해요
    파이프라인의 최종 결과물이 여기 쌓여요
    """
    __tablename__ = "document"

    doc_id       = Column(Integer,     primary_key=True, autoincrement=True)  # 문서 고유번호
    file_name    = Column(String(255), nullable=True)                          # 파일명  예: 계약서.pdf
    file_type    = Column(String(50),  nullable=True)                          # 확장자  예: pdf
    file_size    = Column(String(50),  nullable=True)                          # 파일 크기
    cat_id       = Column(Integer, ForeignKey("category.cat_id"), nullable=False)  # 어떤 분류인지 (Category 연결)
    content_full = Column(Text,        nullable=True)                          # OCR로 뽑은 전체 텍스트
    content_sum  = Column(Text,        nullable=True)                          # Ollama가 만든 요약문
    saved_time   = Column(DateTime,    nullable=True, server_default=func.now())  # 저장된 시간 (자동)
    visible      = Column(Boolean,     nullable=True, default=True)            # False면 삭제된 문서

    # 관계 연결
    분류 = relationship("Category", back_populates="문서목록")
    작업목록 = relationship("Job", back_populates="문서")


class Job(Base):
    """
    [작업 이력 테이블]
    파이프라인이 언제 시작해서 언제 끝났는지 기록해요
    어떤 문서를 처리했는지도 남겨요
    """
    __tablename__ = "job"

    job_id     = Column(Integer,   primary_key=True, autoincrement=True)       # 작업 고유번호
    job_start  = Column(TIMESTAMP, nullable=True)                               # 작업 시작 시간
    job_finish = Column(TIMESTAMP, nullable=True)                               # 작업 완료 시간
    doc_id     = Column(Integer, ForeignKey("document.doc_id"), nullable=True)  # 처리한 문서 번호
    status     = Column(Boolean,   nullable=True, default=False)                # True = 완료, False = 진행중

    # 관계 연결
    문서 = relationship("Document", back_populates="작업목록")