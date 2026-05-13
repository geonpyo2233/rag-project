from __future__ import annotations

from fastapi import FastAPI

from api.routes import router
from config import ensure_directories
from utils.logger import setup_logging


ensure_directories()
setup_logging()

app = FastAPI(
    title="Korean Document Converter Server",
    description="HWP/HWPX/PDF/DOCX document conversion server for Korean document pipelines.",
    version="1.0.0",
)

app.include_router(router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}

