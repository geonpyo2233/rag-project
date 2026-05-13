# Korean Document Converter Server

FastAPI 기반 문서 변환 서버입니다. HWP/HWPX/PDF/DOCX/이미지 파일을 업로드하면 직접 텍스트를 추출하거나 OCR 처리를 위한 PDF/이미지로 변환합니다.

## 지원 형식

| 형식 | 처리 방식 | 결과 |
| --- | --- | --- |
| HWP | 한컴오피스 COM 자동화 | 직접 텍스트 추출 후 PDF 변환 및 OCR 보완 |
| HWPX | ZIP 내부 XML 직접 파싱 | UTF-8 텍스트 추출 |
| PDF | PyMuPDF 직접 텍스트 추출 또는 렌더링 | 내장 텍스트 추출, 부족하면 OCR |
| DOCX | python-docx 직접 파싱 | 문단/표 텍스트 추출 |
| Image | PyMuPDF 변환 및 PaddleOCR | PDF 변환 후 OCR 텍스트 추출 |

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
│   ├── docx_parser.py
│   └── image_converter.py
├── services/
│   ├── convert_service.py
│   ├── file_service.py
│   ├── ocr_service.py
│   └── routing_service.py
├── router/
│   └── document_router.py
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

Windows 환경과 Python 3.10을 권장합니다. HWP 변환은 한컴오피스가 설치된 Windows에서만 동작합니다.

```powershell
cd backend\experiments\hong\document_converter_server
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

서버 실행 후 Swagger 문서는 아래 주소에서 확인할 수 있습니다.

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
    "conversion_type": "hwpx_xml_parser",
    "text_path": "C:\\...\\output\\extracted_text\\sample_abcd1234.txt",
    "extracted_text": "추출된 본문...",
    "ocr_required": false
  }
}
```

## 처리 흐름

```text
업로드 파일 검증
→ uploads/ 저장
→ 확장자별 처리 전략 결정
→ 직접 텍스트 추출 또는 OCR fallback 실행
→ output/extracted_text/에 텍스트 저장
→ JSON 응답 반환
```

## 라우팅 전략

| 형식 | 전략 |
| --- | --- |
| PDF | 내장 텍스트가 충분하면 직접 추출, 부족하면 페이지 이미지 렌더링 후 OCR |
| HWPX | OCR 없이 ZIP 내부 XML 직접 파싱 |
| DOCX | python-docx로 문단과 표 텍스트 직접 추출 |
| HWP | 한컴오피스 COM으로 직접 텍스트 추출을 시도하고 PDF 변환 후 OCR로 보완 |
| Image | 업로드 이미지를 PDF로 변환한 뒤 페이지 이미지로 렌더링하고 OCR 실행 |

응답에는 선택된 전략 정보가 포함됩니다.

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

## 한컴오피스 COM 자동화

HWP 변환은 `win32com.client.gencache.EnsureDispatch("HWPFrame.HwpObject")`를 사용합니다. 따라서 한컴오피스가 설치된 Windows 환경에서만 동작합니다.

안정성을 위해 다음 처리를 포함합니다.

- 변환 대상 파일 존재 여부 확인
- COM 객체 생성 실패 예외 처리
- HWP 창 숨김 처리 시도
- `RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")` 등록 시도
- 변환 작업을 별도 child process에서 실행
- timeout 초과 시 child process 종료
- `Quit()` 및 `CoUninitialize()` 호출
- 변환 결과 PDF의 존재 여부와 파일 크기 검증
- `output/logs/server.log`에 로그 저장

HWP timeout은 환경변수로 조정할 수 있습니다.

```powershell
$env:HWP_TIMEOUT_SECONDS="180"
```

## 주요 환경변수

| 환경변수 | 기본값 | 설명 |
| --- | --- | --- |
| `MAX_UPLOAD_SIZE_MB` | `50` | 업로드 최대 크기 |
| `HWP_TIMEOUT_SECONDS` | `120` | HWP COM 변환 timeout |
| `PDF_RENDER_SCALE` | `2.0` | PyMuPDF 렌더링 배율 |
| `PDF_IMAGE_FORMAT` | `png` | 출력 이미지 형식 |
| `DIRECT_TEXT_MIN_CHARS` | `30` | 직접 추출 텍스트 사용 기준 |
| `OCR_LANG` | `korean` | PaddleOCR 언어 설정 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |

## 운영 메모

- HWP 변환 서버는 Windows 데스크톱 세션 또는 COM 자동화가 가능한 서버 환경에서 운영해야 합니다.
- 한컴오피스 COM 자동화는 서비스 계정 권한, 보안 모듈, 팝업 창에 민감할 수 있습니다.
- 실제 운영에서는 변환 서버와 OCR 서버를 분리하고, 큐 기반 worker 구조로 확장하는 구성을 권장합니다.
