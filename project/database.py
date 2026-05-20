# database.py
# PostgreSQL 연결을 담당하는 파일
# 이 파일 하나만 있으면 어디서든 DB에 접속할 수 있어요

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# .env 파일에서 DB 주소 불러오기
load_dotenv()

# DB 접속 주소 (없으면 기본값 사용)
DB_주소 = os.getenv("DATABASE_URL")
if not DB_주소:
    raise RuntimeError("DATABASE_URL is required in environment (.env)")

# DB 엔진 생성 - 실제로 PostgreSQL에 연결하는 객체
엔진 = create_engine(DB_주소, echo=False)

# 세션 - DB랑 대화할 때 쓰는 창구
세션만들기 = SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=엔진)
# 모든 테이블 클래스가 상속받을 베이스
Base = declarative_base()


def get_db():
    """
    FastAPI 요청마다 자동으로 DB 세션을 열고 닫아주는 함수
    router.py에서 Depends(get_db) 형태로 사용해요
    """
    db = 세션만들기()
    try:
        yield db       # 여기서 router.py한테 세션을 넘겨줌
    finally:
        db.close()     # 요청 끝나면 자동으로 세션 닫힘