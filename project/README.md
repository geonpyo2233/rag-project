# AI 기반 문서 요약 및 카테고리 분류 RAG 시스템

비정형 문서(`.hwp`, `.hwpx`, `.pdf`, `.docx`, `.ppt`, `.pptx`)를 업로드하면
텍스트 추출(OCR 포함) → 벡터화(RAG) → LLM 요약/분류 → DB 저장까지 자동으로 처리하는 시스템입니다.

---

## 주요 기능

- 문서 업로드 및 비동기 처리 (`job_id` 기반 상태 조회)
- 문서 형식별 텍스트 추출
  - PDF: 텍스트 추출 + 필요 시 OCR
  - HWP/HWPX: 본문 추출 + 객체 이미지 OCR 보조
  - DOCX/PPTX: 본문/슬라이드 텍스트 추출
- RAG 파이프라인
  - 텍스트 청킹
  - 임베딩 생성
  - ChromaDB 저장
- LLM 기반
  - 문서 요약
  - 메인/서브 카테고리 분류
- PostgreSQL 메타데이터 저장
- React 기반 웹 UI 제공

---

## 프로젝트 구조 (상세)

```text
project/
├─ main.py                         # FastAPI 엔트리포인트 (API 라우트 + 비동기 작업 시작/조회)
├─ database.py                     # SQLAlchemy 엔진/세션 생성, DB 연결
├─ models.py                       # Category, Document 테이블 정의
├─ llm_chain.py                    # LLM 프롬프트 작성/호출, 요약·카테고리 파싱
├─ rag_pipeline.py                 # 문서 청킹 → 임베딩 → Chroma 저장
├─ document_pipeline.py            # 확장자별 extractor 라우팅 (pdf/hwp/hwpx/docx/ppt/pptx)
├─ check_file.py                   # 파일 유효성 검사 유틸
├─ requirements.txt                # 백엔드 의존성 목록
├─ .env                            # 실행 환경변수 (로컬)
├─ .env.example                    # 환경변수 템플릿
├─ README.md                       # 프로젝트 문서
│
├─ app/
│  ├─ __init__.py
│  ├─ config.py                    # pydantic-settings 설정 객체
│  │                               # (APP_NAME, OLLAMA_*, *_DIR, DATABASE_URL 등)
│  ├─ schemas.py                   # Pydantic 응답 스키마
│  │                               # ProcessStartResponse, JobStatusResponse, ProcessResponse
│  └─ services/
│     ├─ __init__.py
│     └─ pipeline.py               # 서비스형 파이프라인(추출→RAG→LLM→DB 저장) 로직
│
├─ extractors/                     # 문서 형식별 추출 모듈
│  ├─ docx_ext/
│  │  ├─ __init__.py
│  │  ├─ docx_extractor.py         # DOCX 본문/이미지 추출
│  │  └─ docx_ocr.py               # DOCX 이미지 OCR 처리
│  ├─ hwp_ext/
│  │  ├─ __init__.py
│  │  ├─ hwp_extractor.py          # HWP/HWPX 통합 추출 진입점
│  │  ├─ hwp_converter.py          # HWP 텍스트/객체 처리
│  │  ├─ hwpx_parser.py            # HWPX(XML) 파싱
│  │  └─ pdf_converter.py          # 변환/렌더링 보조
│  ├─ pdf_ext/
│  │  ├─ __init__.py
│  │  ├─ pdf_extractor.py          # PDF 텍스트/OCR 추출 및 JSON 생성
│  │  └─ pdf_converter.py          # PDF 페이지 이미지 변환
│  └─ ppt_ext/
│     ├─ __init__.py
│     └─ ppt_extractor.py          # PPT/PPTX 슬라이드 텍스트 추출
│
├─ utils/
│  ├─ __init__.py
│  ├─ file_utils.py                # 파일 경로/이름 유틸
│  └─ logger.py                    # 로거 설정 유틸
│
├─ data/                           # 런타임 데이터 저장소
│  ├─ uploads/                     # 업로드된 원본 파일
│  ├─ ocr_output/                  # extractor 결과 JSON
│  ├─ chroma_db/                   # Chroma 벡터 저장소
│  └─ work/                        # 임시 작업 디렉터리
│
├─ output/                         # 중간 결과물/실험 산출물
│  ├─ text/
│  ├─ json/
│  ├─ images/
│  └─ ...
│
└─ frontend/                       # React + Vite 프론트엔드
   ├─ package.json
   ├─ package-lock.json
   ├─ vite.config.js
   ├─ index.html
   ├─ node_modules/                # 로컬 설치 의존성
   └─ src/
      ├─ main.jsx                  # 프론트 진입점
      ├─ App.jsx                   # 업로드/상태/결과 UI
      ├─ api.js                    # 백엔드 API 호출 모듈
      └─ styles.css                # 화면 스타일
```

---
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

---

## 실행 환경

- Python 3.10+
- PostgreSQL
- Ollama
- (Windows 환경 권장) HWP 변환/추출 관련 도구

---

## 설치 및 실행

### 1) 백엔드 설치

```bash
cd project
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 2) 환경변수 설정

`.env.example`을 `.env`로 복사 후 값 수정:

```bash
# Windows PowerShell
copy .env.example .env
# macOS/Linux
# cp .env.example .env
```

필수 확인 항목:

- `DATABASE_URL`
- `UPLOAD_DIR`
- `WORK_DIR`
- `CHROMA_DIR`
- `OCR_OUTPUT_DIR`
- `OLLAMA_URL`
- `OLLAMA_MODEL`

### 3) Poppler 설치 (Windows, PDF OCR 필수)

`pdf2image`는 내부적으로 Poppler의 `pdfinfo`, `pdftoppm` 실행파일이 필요합니다.

1. Poppler for Windows 다운로드 후 압축 해제
2. 아래 경로를 Windows PATH에 추가

```text
C:\Users\<사용자명>\Downloads\Release-26.02.0-0\poppler-26.02.0\Library\bin
```

3. 새 터미널을 열고 인식 확인

```bash
where.exe pdfinfo
where.exe pdftoppm
python -c "import shutil; print(shutil.which('pdfinfo'))"
```

### 4) Ollama 모델 준비

```bash
ollama pull llama3.1:8b
# 또는 .env의 OLLAMA_MODEL에 맞는 모델
```

### 5) 서버 실행

```bash
uvicorn main:app --reload --port 8000
```

헬스체크:

- `GET http://localhost:8000/health`

### 6) 프론트 실행

```bash
cd frontend
npm install
npm run dev
```

- 프론트 기본 주소: `http://localhost:5173`

---

## API 요약

### 처리 시작

- `POST /api/process/start`
- `multipart/form-data`의 `file` 필드로 업로드

응답 예시:

```json
{
  "job_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

### 상태 조회

- `GET /api/process/{job_id}`

응답 예시(완료):

```json
{
  "job_id": "...",
  "status": "completed",
  "progress": 100,
  "stage": "completed",
  "message": "처리 완료",
  "result": {
    "filename": "sample.hwp",
    "summary": "...",
    "main_category": "기술",
    "sub_category": "AI",
    "category": "기술"
  }
}
```

---

## 트러블슈팅

### 1) Ollama 404 에러

에러 예시:

- `OllamaEndpointNotFoundError ... model is not found`

원인:

- 코드/환경변수의 모델명과 실제 Ollama 설치 모델이 불일치

해결:

1. `.env`의 `OLLAMA_MODEL` 확인
2. `ollama pull <모델명>` 실행
3. 서버 재시작

### 2) `pydantic_settings` 모듈 없음

원인:

- 현재 파이썬 환경에 미설치

해결:

```bash
python -m pip install pydantic-settings
```

### 3) `DATABASE_URL` 관련 오류

원인:

- `.env` 누락/오타 또는 PostgreSQL 미실행

해결:

1. PostgreSQL 실행 확인
2. `DATABASE_URL` 형식 점검
3. 계정/비밀번호/DB명 확인

### 4) `PDFInfoNotInstalledError` (pdf2image / poppler)

에러 예시:

- `Unable to get page count. Is poppler installed and in PATH?`

원인:

- Poppler 미설치 또는 `Library/bin` 경로가 PATH에 없음
- PATH 추가 후 기존 터미널/서버를 재시작하지 않음

해결:

1. Poppler 설치 후 `...\Library\bin`을 PATH에 추가
2. 터미널/uvicorn 프로세스 완전 종료 후 재실행
3. `where.exe pdfinfo`로 인식 여부 확인

---

## 운영 팁

- 설정값은 `.env`를 단일 기준으로 관리
- 모델명/DB URL/경로 하드코딩 금지
- 대용량 문서 처리 시 OCR/임베딩 단계 시간이 길 수 있으므로 polling 유지
- `data/` 디렉터리 용량 주기적 정리 권장

---

## 기술 스택

- Backend: FastAPI, SQLAlchemy
- AI/LLM: LangChain, Ollama
- Vector DB: ChromaDB
- OCR/문서처리: PaddleOCR, pdfplumber, PyMuPDF, python-docx, python-pptx, hwp-extract
- Frontend: React, Vite, Axios
- Database: PostgreSQL

---

## 향후 개선 아이디어

- `langchain_community.Ollama` → `langchain-ollama` 전환
- 에러 메시지/로깅 표준화
- 비동기 작업 큐(Celery/RQ) 도입
- 검색 API 및 관리 UI 확장
- 테스트 코드(단위/통합) 강화

