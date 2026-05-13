from __future__ import annotations

from pathlib import Path

from config import IMAGE_EXTENSIONS, PDF_OUTPUT_DIR
from utils.file_utils import unique_path
from utils.logger import get_logger


logger = get_logger(__name__)


def convert_image_to_pdf(source_path: Path, output_dir: Path = PDF_OUTPUT_DIR) -> Path:
    """Convert an uploaded image into a single-page PDF using PyMuPDF."""
    import fitz

    source_path = source_path.resolve()
    if source_path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError("Image to PDF conversion only supports image files.")
    if not source_path.exists():
        raise FileNotFoundError(f"Image file not found: {source_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = unique_path(output_dir / f"{source_path.stem}.pdf")

    image_document = fitz.open(str(source_path))
    try:
        pdf_bytes = image_document.convert_to_pdf()
    finally:
        image_document.close()

    output_document = fitz.open("pdf", pdf_bytes)
    try:
        output_document.save(str(output_path))
    finally:
        output_document.close()

    logger.info("Converted image to PDF: %s -> %s", source_path, output_path)
    return output_path

