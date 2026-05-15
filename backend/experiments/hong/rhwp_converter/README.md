# RHWP Converter (Single Route)

`hong/rhwp_converter`는 `rhwp` 기반 HWP/HWPX -> PDF 변환 서버입니다.  
운영 엔드포인트는 **`/convert-print-pdf` 하나만** 사용합니다.

## 1) Prerequisites

- Windows
- Python 3.10+
- `rhwp` CLI (PATH 등록)
- Playwright Chromium

## 2) rhwp 설치 (Windows)

1. 다운로드: [rhwp releases](https://github.com/edwardkim/rhwp/releases)
2. 압축 해제 예시:
   - `C:\Users\Zenbook\Downloads\rhwp-v0.7.11-windows-x86_64\rhwp`
3. 실행 파일 확인:
```powershell
Get-ChildItem -Recurse "C:\Users\Zenbook\Downloads\rhwp-v0.7.11-windows-x86_64" -Filter rhwp*.exe
```
4. PATH 등록(현재 사용자):
```powershell
[Environment]::SetEnvironmentVariable(
  "Path",
  [Environment]::GetEnvironmentVariable("Path","User") + ";C:\Users\Zenbook\Downloads\rhwp-v0.7.11-windows-x86_64\rhwp",
  "User"
)
```
5. 새 PowerShell에서 확인:
```powershell
rhwp --help
```

## 3) Install

```powershell
cd C:\Users\Zenbook\Desktop\rag-project\backend\experiments\hong\rhwp_converter
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## 4) Run

```powershell
uvicorn server:app --host 0.0.0.0 --port 8010
```

- Docs: `http://127.0.0.1:8010/docs`
- Health: `GET /health`
- Capabilities: `GET /capabilities`
- Convert (single route): `POST /convert-print-pdf` (multipart `file`)

## 5) Notes

- 변환 파이프라인:
  - 가능하면 `export-png` 우선 사용 (가독성 우선)
  - 실패 시 `export-svg` 폴백
  - Playwright 인쇄로 PDF 생성
- 입력 확장자: `.hwp`, `.hwpx`
