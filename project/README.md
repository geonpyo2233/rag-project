# AI 기반 문서 요약 및 카테고리 분류 RAG 시스템

## 프로젝트 구조

```
project/
├── main.py                        ← FastAPI 서버 진입점
├── database.py                    ← PostgreSQL 연결
├── models.py                      ← DB 테이블 정의
├── llm_chain.py                   ← Ollama 요약/분류
├── rag_pipeline.py                ← 청킹 → 임베딩 → Chroma
├── check_file.py                  ← 입력 파일 검증
├── .env.example                   ← 환경변수 예시
│
├── app/
│   ├── config.py                  ← 설정값 (pydantic-settings)
│   ├── schemas.py                 ← 요청/응답 스키마
│   └── services/
│       └── pipeline.py            ← 전체 파이프라인 오케스트레이터
│
├── extractors/
│   ├── pdf_ext/
│   │   ├── pdf_extractor.py       ← PDF 텍스트/OCR 추출
│   │   └── pdf_converter.py       ← PDF → 이미지 렌더링
│   ├── hwp_ext/
│   │   ├── hwp_extractor.py       ← HWP/HWPX 추출 진입점
│   │   ├── hwp_converter.py       ← HWP → PDF 변환
│   │   └── hwpx_parser.py         ← HWPX XML 파싱
│   ├── docx_ext/
│   │   ├── docx_extractor.py      ← DOCX 텍스트+이미지 OCR
│   │   └── docx_ocr.py            ← DOCX 이미지 OCR
│   └── ppt_ext/
│       └── ppt_extractor.py       ← PPT/PPTX 슬라이드 추출
│
├── data/
│   ├── uploads/                   ← 업로드된 원본 파일
│   ├── ocr_output/                ← OCR 결과 JSON
│   ├── chroma_db/                 ← Chroma 벡터 DB
│   └── work/                      ← 임시 작업 폴더
│
└── frontend/                      ← React + Vite 프론트엔드
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api.js
        └── styles.css
```

## 파이프라인 흐름

```
파일 업로드 (POST /api/process/start)
    │
    ▼
확장자별 Extractor (pdf / hwp / hwpx / docx / ppt / pptx)
    │  └─ 텍스트 추출 + JSON 저장 (data/ocr_output/)
    ▼
RAG Pipeline (rag_pipeline.py)
    │  └─ 청킹 → 임베딩 → Chroma 저장
    ▼
LLM Chain (llm_chain.py)
    │  └─ Ollama → 대분류 / 소분류 / 요약
    ▼
PostgreSQL DB 저장 (Category + Document 테이블)
    │
    ▼
결과 반환 (GET /api/process/{job_id})
```

## 실행 방법

### 백엔드
```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 파일에서 DB 비밀번호 등 수정

# 2. 패키지 설치
pip install fastapi uvicorn pdfplumber pdf2image paddleocr \
            langchain langchain-community langchain-text-splitters \
            sentence-transformers chromadb sqlalchemy psycopg2-binary \
            python-docx python-pptx olefile pillow pymupdf \
            pydantic-settings python-dotenv

# 3. Ollama 실행 (별도 터미널)
ollama run qwen3:8b

# 4. 서버 실행
uvicorn main:app --reload --port 8000
```

### 프론트엔드
```bash
cd frontend
npm install
npm run dev
# http://localhost:5173 접속
```
