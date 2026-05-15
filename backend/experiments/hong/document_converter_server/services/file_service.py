from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from config import MAX_UPLOAD_SIZE_BYTES, MAX_UPLOAD_SIZE_MB, SUPPORTED_EXTENSIONS, UPLOAD_DIR
from utils.file_utils import sanitize_filename
from utils.logger import get_logger


logger = get_logger(__name__)


async def save_upload_file(upload_file: UploadFile) -> Path:
    """Validate and save an uploaded file with size limiting."""
    original_name = upload_file.filename or ""
    safe_name = sanitize_filename(original_name)
    suffix = Path(safe_name).suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"지원하지 않는 파일 형식입니다. 허용 형식: {allowed}")

    target_path = UPLOAD_DIR / f"{Path(safe_name).stem}_{uuid4().hex[:12]}{suffix}"
    target_path.parent.mkdir(parents=True, exist_ok=True)

    total_size = 0
    try:
        with target_path.open("wb") as output:
            while chunk := await upload_file.read(1024 * 1024):
                total_size += len(chunk)
                if total_size > MAX_UPLOAD_SIZE_BYTES:
                    raise ValueError(f"업로드 파일 크기는 {MAX_UPLOAD_SIZE_MB}MB를 초과할 수 없습니다.")
                output.write(chunk)
    except Exception:
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        raise
    finally:
        await upload_file.close()

    if total_size == 0:
        target_path.unlink(missing_ok=True)
        raise ValueError("빈 파일은 변환할 수 없습니다.")

    logger.info("Saved upload: %s (%s bytes)", target_path, total_size)
    return target_path
