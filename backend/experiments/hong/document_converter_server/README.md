# Korean Document Converter Server

Python 3.10과 FastAPI 기반의 한국형 문서 변환 서버입니다. OCR 엔진을 직접 구현하지 않고, HWP/HWPX/PDF/DOCX 문서를 OCR 시스템에 전달하기 좋은 형태로 변환하거나 텍스트를 추출하는 데 집중합니다.

## 지원 포맷

| 포맷 | 처리 방식 | 결과 |
| --- | --- | --- |
| HWP | 한컴오피스 COM 자동화 | PDF 변환 후 페이지 이미지 생성 |
| HWPX | ZIP 내부 XML 직접 파싱 | UTF-8 텍스트 추출 |
| PDF | PyMuPDF 렌더링 | 페이지별 고해상도 이미지 생성 |
| DOCX | python-docx 직접 파싱 | UTF-8 텍스트 추출 |
| Image | PyMuPDF + PaddleOCR | PDF 변환 후 OCR 텍스트 추출 |

## 폴더 구조

```text
document_converter_server/
├── app.py
├── config.py
├── requirements.txt
├── README.md
├── api/
│   └── routes.py
├── converters/
│   ├── hwp_converter.py
│   ├── hwpx_parser.py
│   ├── pdf_converter.py
│   └── docx_parser.py
├── services/
│   ├── convert_service.py
│   └── file_service.py
├── utils/
│   ├── logger.py
│   ├── file_utils.py
│   └── response.py
├── uploads/
├── output/
│   ├── pdf/
│   ├── images/
│   ├── extracted_text/
│   └── logs/
└── temp/
```

## 실행 방법

Windows에서 Python 3.10 가상환경을 권장합니다.

```powershell
cd document_converter_server
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Swagger 문서는 서버 실행 후 다음 주소에서 확인합니다.

```text
http://localhost:8000/docs
```

상태 확인:

```powershell
curl http://localhost:8000/health
```

## API 사용 예시

```powershell
curl -X POST "http://localhost:8000/convert" `
  -F "file=@C:\docs\sample.hwpx" `
  -F "render_scale=2.5"
```

응답 예시:

```json
{
  "success": true,
  "timestamp": "2026-05-13T00:00:00+00:00",
  "data": {
    "status": "converted",
    "source_file": "C:\\...\\uploads\\sample_abcd1234.hwpx",
    "source_extension": ".hwpx",
    "log_file": "C:\\...\\output\\logs\\server.log",
    "conversion_type": "hwpx_xml_text_extraction",
    "pdf_path": null,
    "image_paths": [],
    "text_path": "C:\\...\\output\\extracted_text\\sample_abcd1234.txt",
    "extracted_text": "추출된 본문..."
  }
}
```

## 변환 흐름

```text
사용자 업로드
↓
확장자 및 파일 크기 검증
↓
uploads/ 저장
↓
document_router에서 문서 처리 방식 판단
↓
직접 텍스트 추출 가능 여부 확인
↓
YES → parser/direct extraction
NO  → OCR fallback용 이미지 생성
↓
JSON 응답으로 결과 경로와 로그 경로 반환
```

## Hybrid Document Pipeline

이 서버는 문서 유형에 따라 직접 추출을 우선하고, 텍스트가 없거나 부족한 경우에만 OCR fallback이 가능하도록 결과 이미지를 생성합니다.

| 포맷 | 라우팅 방식 |
| --- | --- |
| PDF | `page.get_text()`로 내장 텍스트를 먼저 확인하고, 기준 글자 수 미만이면 페이지 이미지를 생성합니다. |
| HWPX | OCR을 사용하지 않고 ZIP 내부 XML을 직접 파싱합니다. |
| DOCX | `python-docx`로 문단과 표 텍스트를 직접 추출합니다. |
| HWP | 한컴 COM으로 직접 텍스트 추출을 먼저 시도하고, 실패하거나 텍스트가 부족하면 PDF 변환 후 이미지를 생성합니다. |
| Image | 업로드 이미지를 PDF로 변환한 뒤 페이지 이미지로 렌더링하고 PaddleOCR을 실행합니다. |

응답에는 선택된 라우팅 전략이 포함됩니다.

```json
{
  "route": {
    "strategy": "pdf_direct_text",
    "reason": "PDF contains enough embedded text for direct extraction.",
    "ocr_required": false,
    "text_length": 1200,
    "metadata": {
      "threshold": 30
    }
  }
}
```

OCR fallback이 실행되면 `ocr_status`는 `completed`가 되고, `ocr_result`에 PaddleOCR 결과가 포함됩니다.

```json
{
  "conversion_type": "image_to_pdf_ocr",
  "ocr_required": true,
  "ocr_status": "completed",
  "ocr_result": {
    "engine": "paddleocr",
    "lang": "korean",
    "page_count": 1
  }
}
```

## 한컴 COM 자동화 설명

HWP 변환은 `win32com.client.gencache.EnsureDispatch("HWPFrame.HwpObject")`를 사용합니다. 한컴오피스가 설치된 Windows 서버에서만 동작합니다.

실무 안정성을 위해 다음을 반영했습니다.

- 변환 전 파일 존재 여부 확인
- COM 객체 생성 실패 예외 처리
- HWP 창 숨김 처리 시도
- `RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")` 등록 시도
- 변환 프로세스를 별도 child process로 실행
- timeout 초과 시 child process 종료
- `Quit()` 및 `CoUninitialize()` 호출
- 변환 결과 PDF 존재 여부와 크기 검증
- `output/logs/server.log`에 로그 저장

환경변수로 HWP timeout을 조정할 수 있습니다.

```powershell
$env:HWP_TIMEOUT_SECONDS="180"
```

## HWPX XML 파싱 설명

HWPX는 ZIP 기반 XML 문서이므로 OCR을 사용하지 않습니다. `zipfile`로 내부 XML을 열고, `xml.etree.ElementTree`로 section XML을 파싱합니다.

파싱 과정:

1. ZIP 파일 여부 검증
2. section/bodytext XML 후보 탐색
3. 문단 태그 중심으로 텍스트 수집
4. 줄바꿈 태그 복원
5. 공백과 빈 줄 정리
6. `output/extracted_text/`에 UTF-8 텍스트 저장

## 주요 모듈 역할

| 모듈 | 역할 |
| --- | --- |
| `app.py` | FastAPI 앱 생성, 라우터 연결, health check |
| `config.py` | 경로, 업로드 크기, 렌더링 배율, timeout 설정 |
| `api/routes.py` | `/convert` 업로드 API와 예외 응답 |
| `services/file_service.py` | 업로드 파일 검증 및 저장 |
| `services/convert_service.py` | 확장자별 변환 파이프라인 분기 |
| `converters/hwp_converter.py` | 한컴 COM 기반 HWP to PDF 변환 |
| `converters/hwpx_parser.py` | HWPX 내부 XML 텍스트 추출 |
| `converters/pdf_converter.py` | PyMuPDF 기반 PDF 페이지 이미지 렌더링 |
| `converters/docx_parser.py` | DOCX 문단/표 텍스트 추출 |
| `utils/logger.py` | logging 설정과 파일 로그 저장 |
| `utils/file_utils.py` | 파일명 정리, 중복 경로 처리, 텍스트 저장 |
| `utils/response.py` | 공통 JSON 응답 포맷 |

## 설정

| 환경변수 | 기본값 | 설명 |
| --- | --- | --- |
| `MAX_UPLOAD_SIZE_MB` | `50` | 업로드 최대 크기 |
| `HWP_TIMEOUT_SECONDS` | `120` | HWP COM 변환 timeout |
| `PDF_RENDER_SCALE` | `2.0` | PyMuPDF 렌더링 배율 |
| `PDF_IMAGE_FORMAT` | `png` | 출력 이미지 포맷 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |

## 운영 메모

- HWP 변환 서버는 Windows 데스크톱 세션 또는 COM 자동화가 가능한 서버 환경에서 운영해야 합니다.
- 한컴오피스 COM 자동화는 서비스 계정 권한, 보안 모듈, 팝업 창에 민감합니다.
- 실제 운영에서는 변환 서버를 OCR 서버와 분리하고, 큐 기반 작업 처리나 별도 worker 프로세스로 확장하는 구성을 권장합니다.
- 이 서버는 OCR 엔진을 포함하지 않습니다. HWP/PDF 결과 이미지를 OCR 시스템에 전달하기 위한 변환 계층입니다.
