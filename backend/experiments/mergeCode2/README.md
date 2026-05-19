# mergeCode2

문서(OCR/텍스트 추출) 파이프라인에 웹 UI를 붙인 실험 프로젝트입니다.

- 백엔드: FastAPI (`api_server.py`)
- 프론트엔드: React + Vite (`frontend/`)
- 문서 처리: `pipelines/document_pipeline.py` + `extractors/*`

## 현재 동작 범위

- 업로드 지원: `.hwp`, `.hwpx`, `.pdf`, `.docx`, `.ppt`, `.pptx`
- 비동기 처리 API: `job_id` 발급 후 상태 폴링
- 결과 응답: `filename`, `summary`, `category`

주의:
- 현재 `summary`는 추출 텍스트 기반의 간단 요약(앞부분)입니다.
- 현재 `category`는 확장자 기반 분류입니다.
- 고도화된 LLM 요약/분류 로직은 아직 미연결 상태입니다.

## 프로젝트 구조

```text
mergeCode2/
  api_server.py
  config.py
  requirements.txt
  data/
    uploads/
  extractors/
  pipelines/
  services/
  utils/
  frontend/
    src/
    package.json
```

## 빠른 실행

### 1) 백엔드 실행

```powershell
cd C:\Users\Zenbook\Desktop\rag-project\backend\experiments\mergeCode2
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3.10 -m pip install --upgrade pip
py -3.10 -m pip install -r requirements.txt
py -3.10 -m uvicorn api_server:app --reload --port 8000
```

헬스체크:
- `http://localhost:8000/health`

### 2) 프론트엔드 실행

새 터미널에서:

```powershell
cd C:\Users\Zenbook\Desktop\rag-project\backend\experiments\mergeCode2\frontend
npm install
npm run dev
```

접속:
- `http://localhost:5173`

## API 명세

### `POST /api/process/start`

업로드 파일 처리 작업 시작

- Request: `multipart/form-data`
  - `file`: 업로드 파일
- Response:

```json
{
  "job_id": "string"
}
```

### `GET /api/process/{job_id}`

처리 상태 조회

- Response 예시:

```json
{
  "job_id": "string",
  "status": "queued | running | completed | failed",
  "progress": 0,
  "stage": "queued | extract | postprocess | completed | failed",
  "message": "",
  "result": {
    "filename": "sample.pdf",
    "summary": "...",
    "category": "PDF"
  }
}
```

## 개발 메모

- 업로드 파일은 `data/uploads/`에 저장됩니다.
- 런타임 산출물은 `output/`에 생성될 수 있습니다.
- `.gitignore`에서 `frontend/node_modules`, `output`, `data/uploads` 등을 무시하도록 설정돼 있습니다.

## 트러블슈팅

- PowerShell 실행 정책 오류:
  - 관리자 PowerShell에서 `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`
- `npm`/`py` 명령 인식 오류:
  - Node.js, Python 3.10 설치 및 PATH 확인
- 포트 충돌:
  - 백엔드 `--port` 또는 프론트 Vite 포트 변경

## 향후 개선 포인트

1. 요약/분류 LLM 연동
2. PPT/PPTX 실제 파서 구현
3. 테스트 코드(단위/통합) 추가
4. DB 저장 구조 연동 (`Doc`, `Job`, `Category`, `Vector`)
