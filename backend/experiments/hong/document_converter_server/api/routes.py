from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from config import PDF_RENDER_SCALE
from services.convert_service import convert_document
from services.file_service import save_upload_file
from utils.logger import get_logger
from utils.response import error_response, success_response


router = APIRouter(tags=["conversion"])
logger = get_logger(__name__)


@router.post("/convert")
async def convert(
    file: Annotated[UploadFile, File(description="hwp, hwpx, pdf, docx, or image file")],
    render_scale: Annotated[
        float | None,
        Form(description="PDF rendering scale. 2.0 is a practical default for OCR pipelines."),
    ] = None,
) -> dict:
    """Upload a document and convert it into OCR-ready or text-extracted output."""
    try:
        saved_path = await save_upload_file(file)
        result = convert_document(
            saved_path,
            render_scale=render_scale or PDF_RENDER_SCALE,
        )
        return success_response(result)
    except ValueError as exc:
        logger.warning("Invalid conversion request: %s", exc)
        raise HTTPException(status_code=400, detail=error_response(str(exc)))
    except TimeoutError as exc:
        logger.exception("Conversion timed out")
        raise HTTPException(status_code=504, detail=error_response(str(exc)))
    except Exception as exc:
        logger.exception("Conversion failed")
        raise HTTPException(
            status_code=500,
            detail=error_response("문서 변환 중 오류가 발생했습니다.", error=str(exc)),
        )
