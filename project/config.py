# ==============================
# config.py  –  전체 프로젝트 공통 설정
# ==============================
# 모든 extractor와 서비스가 이 파일 하나에서 설정값을 가져온다.

from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

# ── 프로젝트 루트 ─────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent

# ── 데이터 디렉터리 ───────────────────────────────────────────────────
OUTPUT_DIR      = BASE_DIR / "data" / "output"
TEXT_OUTPUT_DIR = OUTPUT_DIR / "text"
IMAGE_OUTPUT_DIR= OUTPUT_DIR / "images"
PDF_OUTPUT_DIR  = OUTPUT_DIR / "pdf"
TEMP_DIR        = BASE_DIR / "data" / "work"

# 실행 시 자동 생성
for _d in [OUTPUT_DIR, TEXT_OUTPUT_DIR, IMAGE_OUTPUT_DIR, PDF_OUTPUT_DIR, TEMP_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ── 지원 확장자 ───────────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = {".pdf", ".hwp", ".hwpx", ".docx", ".ppt", ".pptx"}

# ── PDF 렌더링 설정 ───────────────────────────────────────────────────
PDF_RENDER_SCALE  = 2.0          # 페이지 이미지 렌더링 배율
PDF_IMAGE_FORMAT  = "png"        # 저장 포맷

# ── OCR 공통 설정 ─────────────────────────────────────────────────────
OCR_LANGUAGE      = "korean"     # PaddleOCR 언어
OCR_USE_GPU       = False        # GPU 사용 여부

# ── DOCX OCR 설정 ─────────────────────────────────────────────────────
DOCX_OCR_UPSCALE_ENABLED = True  # 이미지 업스케일 여부
DOCX_OCR_UPSCALE_FACTOR  = 2     # 업스케일 배율

# ── HWP 설정 ──────────────────────────────────────────────────────────
HWP_TIMEOUT_SECONDS   = 60       # HWP → PDF 변환 타임아웃 (초)
DIRECT_TEXT_MIN_CHARS = 100      # 직접 추출 텍스트 최소 길이 (이하면 OCR fallback)

# ── LLM 설정 ──────────────────────────────────────────────────────────
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL",   "qwen3:8b")
OLLAMA_URL     = os.getenv("OLLAMA_URL",     "http://localhost:11434")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT_SEC", "300"))

# ── DB 설정 ───────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:1234@localhost:5432/rag_db"
)

# ── 임베딩 설정 ───────────────────────────────────────────────────────
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "jhgan/ko-sroberta-multitask")
