from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from rhwp_convert import convert_hwp_to_pdf_with_browser_print


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output_pdf"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="RHWP HWP->PDF Converter", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/capabilities")
def capabilities() -> dict[str, bool]:
    rhwp_exists = shutil.which("rhwp") is not None
    return {"rhwp_in_path": rhwp_exists}


@app.post("/convert-print-pdf")
async def convert_upload_print(file: UploadFile = File(...), keep_output: bool = Form(True)) -> FileResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".hwp", ".hwpx"}:
        raise HTTPException(status_code=400, detail="Only .hwp/.hwpx files are supported.")

    token = uuid.uuid4().hex[:12]
    input_path = UPLOAD_DIR / f"{Path(file.filename or 'input').stem}_{token}{suffix}"
    output_path = OUTPUT_DIR / f"{input_path.stem}_print.pdf"

    try:
        with input_path.open("wb") as fp:
            fp.write(await file.read())
        pdf_path = await convert_hwp_to_pdf_with_browser_print(input_path, output_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}") from exc
    finally:
        input_path.unlink(missing_ok=True)

    headers = {}
    if not keep_output:
        headers["X-Temp-Output"] = "true"

    return FileResponse(
        str(pdf_path),
        media_type="application/pdf",
        filename=pdf_path.name,
        headers=headers,
    )
