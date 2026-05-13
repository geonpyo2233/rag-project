from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
PDF_OUTPUT_DIR = OUTPUT_DIR / "pdf"
IMAGE_OUTPUT_DIR = OUTPUT_DIR / "images"
TEXT_OUTPUT_DIR = OUTPUT_DIR / "extracted_text"
LOG_OUTPUT_DIR = OUTPUT_DIR / "logs"
TEMP_DIR = BASE_DIR / "temp"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
SUPPORTED_EXTENSIONS = {".hwp", ".hwpx", ".pdf", ".docx", *IMAGE_EXTENSIONS}

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

HWP_TIMEOUT_SECONDS = int(os.getenv("HWP_TIMEOUT_SECONDS", "120"))
PDF_RENDER_SCALE = float(os.getenv("PDF_RENDER_SCALE", "2.0"))
PDF_IMAGE_FORMAT = os.getenv("PDF_IMAGE_FORMAT", "png").lower()
DIRECT_TEXT_MIN_CHARS = int(os.getenv("DIRECT_TEXT_MIN_CHARS", "30"))
OCR_LANG = os.getenv("OCR_LANG", "korean")
OCR_USE_ANGLE_CLS = os.getenv("OCR_USE_ANGLE_CLS", "true").lower() == "true"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = LOG_OUTPUT_DIR / "server.log"


def ensure_directories() -> None:
    """Create runtime directories used by the conversion server."""
    for directory in (
        UPLOAD_DIR,
        PDF_OUTPUT_DIR,
        IMAGE_OUTPUT_DIR,
        TEXT_OUTPUT_DIR,
        LOG_OUTPUT_DIR,
        TEMP_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
