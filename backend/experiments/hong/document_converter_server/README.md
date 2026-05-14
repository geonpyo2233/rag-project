# Korean Document Converter Server

FastAPI 기반 문서 변환 서버입니다.  
`HWP / HWPX / PDF / DOCX / 이미지` 업로드 시, 문서 상태에 맞춰 직접 텍스트 추출 또는 OCR을 수행합니다.

## 핵심 동작

- 라우터(`router/document_router.py`)가 파일 유형/텍스트 품질을 보고 전략을 선택합니다.
- HWP는 직접 텍스트 추출 성공 시 우선 사용하고, 필요할 때만 OCR을 보강합니다.
- OCR 결과는 후처리/중복 제거를 거쳐 `output/extracted_text/*.txt`로 저장됩니다.

## 지원 포맷

- `.hwp`
- `.hwpx`
- `.pdf`
- `.docx`
- 이미지: `.png`, `.jpg`, `.jpeg`, `.bmp`, `.tif`, `.tiff`

## HWP 라우팅 전략 (최신)

1. 직접 텍스트 추출 시도 (`extract_hwp_text`)
   - OLE 파서 우선
   - 실패 시 COM(`SaveAs("TEXT")`) fallback
2. 추출 텍스트 길이가 `DIRECT_TEXT_MIN_CHARS` 이상이면 직접 텍스트 사용
3. 이미지/객체가 감지되면 `hwp_direct_text_with_ocr`로 OCR 보강
4. 직접 추출 실패 또는 텍스트 부족 시 `hwp_to_pdf_ocr_fallback`

`route.metadata.reason_code` 예시:

- `direct_extraction_success`
- `image_or_scan_likely`
- `text_not_found`
- `direct_extraction_failed`

## OCR 보강 방식

- PDF 렌더링 후 PaddleOCR 수행
- 타일 OCR(`OCR_TILE_MODE`) 지원
- `hwp_direct_text_with_ocr`에서는:
  - PDF 텍스트 레이어 영역과 겹치는 OCR 라인 제거
  - 직접 추출 텍스트와 중복되는 OCR 라인 제거
  - 품질 낮은 OCR 라인 필터링(confidence/문자비율 기반)
- 최종 병합 포맷:
  - `[DIRECT_TEXT]`
  - `[OCR_TEXT]`

## 주요 API

- `GET /health`
- `POST /convert`
  - Form field:
    - `file`: 업로드 파일
    - `render_scale`(optional): PDF 렌더링 배율
      - Swagger 설명: `6.25 (~450 DPI)`가 현재 기본값

## 실행 방법

```powershell
cd backend\experiments\hong\document_converter_server
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Swagger UI:

- http://localhost:8000/docs

## 기본 설정값 (`config.py`)

- `PDF_RENDER_SCALE=6.25`
- `DIRECT_TEXT_MIN_CHARS=30`
- `OCR_DROP_SCORE=0.4`
- `OCR_QUALITY_MODE=accurate`
- `OCR_TILE_MODE=true`
- `OCR_TILE_HEIGHT=800`
- `OCR_TILE_OVERLAP=360`
- `OCR_TILE_MIN_HEIGHT=1200`
- `HWP_TIMEOUT_SECONDS=120`

## 자동화 스크립트

한글 COM 자동화 보안 모듈 등록용 스크립트:

- `scripts/setup_hwp_automation.ps1`
- `scripts/setup_hwp_automation_oneclick.bat`

## 출력 경로

- 변환 텍스트: `output/extracted_text/`
- 렌더 이미지: `output/images/`
- OCR 시각화: `output/ocr_visualizations/`
- 로그: `output/logs/server.log`
