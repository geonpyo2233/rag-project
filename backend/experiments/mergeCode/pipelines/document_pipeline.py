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
    extension = file_path.suffix.lower()

    print("\n==============================")
    print(f"파일 처리 시작: {file_path.name}")
    print(f"확장자: {extension}")
    print("==============================")

    if extension == ".docx":
        docx_extractor(file_path)

    elif extension == ".pdf":
        pdf_extractor(file_path)

    elif extension in [".ppt", ".pptx"]:
        ppt_extractor(file_path)

    elif extension in [".hwp", ".hwpx"]:
        hwp_extractor(file_path)

    else:
        print("지원하지 않는 확장자")