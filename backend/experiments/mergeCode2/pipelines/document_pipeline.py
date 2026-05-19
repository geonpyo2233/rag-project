from pathlib import Path

from extractors.docx_ext.docx_extractor import docx_extractor
from extractors.hwp_ext.hwp_extractor import hwp_extractor
from extractors.pdf_ext.pdf_extractor import pdf_extractor
from extractors.ppt_ext.ppt_extractor import ppt_extractor


def run_document_pipeline(file_path: Path):
    """Route a document to the matching extractor and return extraction payload."""
    extension = file_path.suffix.lower()

    print("\n==============================")
    print(f"파일 처리 시작: {file_path.name}")
    print(f"확장자: {extension}")
    print("==============================")

    if extension == ".docx":
        return docx_extractor(file_path)
    if extension == ".pdf":
        return pdf_extractor(file_path)
    if extension in [".ppt", ".pptx"]:
        return ppt_extractor(file_path)
    if extension in [".hwp", ".hwpx"]:
        return hwp_extractor(file_path)

    raise ValueError(f"Unsupported extension: {extension}")
