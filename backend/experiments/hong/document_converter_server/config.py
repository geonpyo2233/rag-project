from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
PDF_OUTPUT_DIR = OUTPUT_DIR / "pdf"
IMAGE_OUTPUT_DIR = OUTPUT_DIR / "images"
TEXT_OUTPUT_DIR = OUTPUT_DIR / "extracted_text"
OCR_VISUALIZATION_DIR = OUTPUT_DIR / "ocr_visualizations"
LOG_OUTPUT_DIR = OUTPUT_DIR / "logs"
TEMP_DIR = BASE_DIR / "temp"

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
SUPPORTED_EXTENSIONS = {".hwp", ".hwpx", ".pdf", ".docx", *IMAGE_EXTENSIONS}

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

HWP_TIMEOUT_SECONDS = int(os.getenv("HWP_TIMEOUT_SECONDS", "120"))
HWP_OCR_SUPPLEMENT = os.getenv("HWP_OCR_SUPPLEMENT", "false").lower() == "true"
PDF_RENDER_SCALE = float(os.getenv("PDF_RENDER_SCALE", "6.25"))  # 렌더링 450 DPI
PDF_IMAGE_FORMAT = os.getenv("PDF_IMAGE_FORMAT", "png").lower()
DIRECT_TEXT_MIN_CHARS = int(os.getenv("DIRECT_TEXT_MIN_CHARS", "30"))
OCR_LANG = os.getenv("OCR_LANG", "korean")
OCR_USE_ANGLE_CLS = os.getenv("OCR_USE_ANGLE_CLS", "true").lower() == "true"
OCR_DET_LIMIT_SIDE_LEN = int(os.getenv("OCR_DET_LIMIT_SIDE_LEN", "2400"))
OCR_DROP_SCORE = float(os.getenv("OCR_DROP_SCORE", "0.4"))
OCR_QUALITY_MODE = os.getenv("OCR_QUALITY_MODE", "accurate").lower()
OCR_SAVE_PREPROCESSED = os.getenv("OCR_SAVE_PREPROCESSED", "false").lower() == "true"
OCR_TILE_MODE = os.getenv("OCR_TILE_MODE", "true").lower() == "true"
OCR_TILE_HEIGHT = int(os.getenv("OCR_TILE_HEIGHT", "800"))
OCR_TILE_OVERLAP = int(os.getenv("OCR_TILE_OVERLAP", "360"))
OCR_TILE_MIN_HEIGHT = int(os.getenv("OCR_TILE_MIN_HEIGHT", "1200"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = LOG_OUTPUT_DIR / "server.log"


def ensure_directories() -> None:
    """Create runtime directories used by the conversion server."""
    for directory in (
        UPLOAD_DIR,
        PDF_OUTPUT_DIR,
        IMAGE_OUTPUT_DIR,
        TEXT_OUTPUT_DIR,
        OCR_VISUALIZATION_DIR,
        LOG_OUTPUT_DIR,
        TEMP_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
