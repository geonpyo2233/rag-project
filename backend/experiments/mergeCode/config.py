from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"


# ==============================
# OCR 설정
# ==============================

OCR_LANGUAGE = "korean"
OCR_USE_GPU = False
DOCX_OCR_UPSCALE_ENABLED = True
DOCX_OCR_UPSCALE_FACTOR = 2

# Ye-rim OCR service compatibility settings.
OCR_LANG = OCR_LANGUAGE
OCR_USE_ANGLE_CLS = True
OCR_DET_LIMIT_SIDE_LEN = 2400
OCR_DROP_SCORE = 0.4
OCR_QUALITY_MODE = "accurate"
OCR_SAVE_PREPROCESSED = False
OCR_TILE_MODE = True
OCR_TILE_HEIGHT = 800
OCR_TILE_OVERLAP = 360
OCR_TILE_MIN_HEIGHT = 1200


# ==============================
# HWP/HWPX 설정
# ==============================

DIRECT_TEXT_MIN_CHARS = 30
HWP_TIMEOUT_SECONDS = 120
HWP_OCR_SUPPLEMENT = False
PDF_RENDER_SCALE = 6.25
PDF_IMAGE_FORMAT = "png"


# ==============================
# Chunk 설정
# ==============================

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


# ==============================
# 임베딩 모델 설정
# ==============================

EMBEDDING_MODEL_NAME = (
    "jhgan/ko-sroberta-multitask"
)


# ==============================
# 지원 확장자 설정
# ==============================

SUPPORTED_EXTENSIONS = {
    ".docx",
    ".hwp",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".pptx",
    ".hwpx",
}


# ==============================
# 출력 폴더 설정
# ==============================

OUTPUT_TEXT_DIR = "text"
OUTPUT_JSON_DIR = "json"
OUTPUT_CHUNK_DIR = "chunks"

TEXT_OUTPUT_DIR = OUTPUT_DIR / OUTPUT_TEXT_DIR
PDF_OUTPUT_DIR = OUTPUT_DIR / "pdf"
IMAGE_OUTPUT_DIR = OUTPUT_DIR / "images"
OCR_VISUALIZATION_DIR = OUTPUT_DIR / "ocr_visualizations"
TEMP_DIR = OUTPUT_DIR / "temp"
LOG_OUTPUT_DIR = OUTPUT_DIR / "logs"
LOG_FILE = LOG_OUTPUT_DIR / "merge_pipeline.log"
LOG_LEVEL = "INFO"


def ensure_directories():
    for directory in (
        TEXT_OUTPUT_DIR,
        PDF_OUTPUT_DIR,
        IMAGE_OUTPUT_DIR,
        OCR_VISUALIZATION_DIR,
        TEMP_DIR,
        LOG_OUTPUT_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
