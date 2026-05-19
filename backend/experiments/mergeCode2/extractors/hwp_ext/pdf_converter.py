from __future__ import annotations

from pathlib import Path

from config import IMAGE_OUTPUT_DIR, PDF_IMAGE_FORMAT, PDF_RENDER_SCALE
from utils.file_utils import unique_path
from utils.logger import get_logger


logger = get_logger(__name__)


def extract_pdf_text(source_path: Path) -> str:
    """Extract embedded text from a PDF before deciding whether OCR is needed."""
    import fitz

    source_path = source_path.resolve()
    if source_path.suffix.lower() != ".pdf":
        raise ValueError("PDF text extraction only supports .pdf files.")
    if not source_path.exists():
        raise FileNotFoundError(f"PDF file not found: {source_path}")

    page_texts: list[str] = []
    with fitz.open(source_path) as document:
        for page in document:
            text = page.get_text("text").strip()
            if text:
                page_texts.append(text)

    extracted_text = "\n\n".join(page_texts).strip()
    logger.info("Extracted %s embedded text chars from PDF: %s", len(extracted_text), source_path)
    return extracted_text


def render_pdf_to_images(
    source_path: Path,
    output_dir: Path = IMAGE_OUTPUT_DIR,
    scale: float = PDF_RENDER_SCALE,
    image_format: str = PDF_IMAGE_FORMAT,
) -> list[Path]:
    """Render each PDF page to a high-resolution image using PyMuPDF."""
    import fitz

    source_path = source_path.resolve()
    if source_path.suffix.lower() != ".pdf":
        raise ValueError("PDF 렌더링은 .pdf 파일만 처리합니다.")
    if not source_path.exists():
        raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {source_path}")
    if scale <= 0:
        raise ValueError("PDF 렌더링 배율은 0보다 커야 합니다.")

    document_output_dir = output_dir / source_path.stem
    document_output_dir.mkdir(parents=True, exist_ok=True)

    output_paths: list[Path] = []
    matrix = fitz.Matrix(scale, scale)

    with fitz.open(source_path) as document:
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            output_path = unique_path(
                document_output_dir / f"page_{page_index + 1:04d}.{image_format}"
            )
            pixmap.save(str(output_path))
            output_paths.append(output_path)

    logger.info("Rendered %s PDF pages: %s", len(output_paths), source_path)
    return output_paths
