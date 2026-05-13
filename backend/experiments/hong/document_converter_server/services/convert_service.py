from __future__ import annotations

from pathlib import Path

from services.routing_service import process_document_with_routing
from utils.logger import get_logger


logger = get_logger(__name__)


def convert_document(source_path: Path, render_scale: float) -> dict:
    """Keep the existing service entrypoint while using the hybrid routing pipeline."""
    source_path = source_path.resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Uploaded file not found: {source_path}")

    logger.info("Dispatching conversion through routing pipeline: %s", source_path)
    return process_document_with_routing(source_path, render_scale=render_scale)
