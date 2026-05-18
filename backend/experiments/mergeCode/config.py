# ==============================
# OCR 설정
# ==============================

OCR_LANGUAGE = "korean"
OCR_USE_GPU = False


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