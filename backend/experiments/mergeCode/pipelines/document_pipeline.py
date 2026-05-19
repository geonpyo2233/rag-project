from pathlib import Path

from extractors.docx_ext.docx_extractor import (
    docx_extractor
)
from extractors.pdf_ext.pdf_extractor import (
    pdf_extractor
)

from extractors.ppt_ext.ppt_extractor import (
    ppt_extractor
)

from extractors.hwp_ext.hwp_extractor import (
    hwp_extractor
)


def run_document_pipeline(file_path: Path):
    """입력 파일 확장자에 맞는 extractor로 작업을 위임하는 공통 진입점."""
    extension = file_path.suffix.lower()

    print("\n==============================")
    print(f"파일 처리 시작: {file_path.name}")
    print(f"확장자: {extension}")
    print("==============================")

    # DOCX: 문단/표 직접 추출 + 내부 이미지 OCR.
    if extension == ".docx":
        docx_extractor(file_path)

    # PDF: PDF 전용 extractor에서 직접 텍스트/OCR 처리를 담당한다.
    elif extension == ".pdf":
        pdf_extractor(file_path)

    # PPT/PPTX: 슬라이드 텍스트와 이미지 OCR 처리를 담당한다.
    elif extension in [".ppt", ".pptx"]:
        ppt_extractor(file_path)

    # HWP/HWPX: 한글 문서 직접 추출 또는 객체 이미지 OCR 처리를 담당한다.
    elif extension in [".hwp", ".hwpx"]:
        hwp_extractor(file_path)

    else:
        print("지원하지 않는 확장자")
