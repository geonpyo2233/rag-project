# ==============================
# document_pipeline.py  –  확장자별 extractor 퍼널
# ==============================
from pathlib import Path

from extractors.docx_ext.docx_extractor import docx_extractor
from extractors.pdf_ext.pdf_extractor import pdf_extractor
from extractors.ppt_ext.ppt_extractor import ppt_extractor
from extractors.hwp_ext.hwp_extractor import hwp_extractor


def run_document_pipeline(file_path: Path) -> dict:
    """
    입력 파일 확장자에 맞는 extractor를 실행하고 결과를 반환한다.
    반환값은 최소한 {"text": str} 을 포함하며,
    pdf_extractor는 {"json_path": Path, "text": str, ...} 를 반환한다.
    """
    extension = file_path.suffix.lower()

    print("\n==============================")
    print(f"파일 처리 시작: {file_path.name}")
    print(f"확장자: {extension}")
    print("==============================")

    if extension == ".pdf":
        return pdf_extractor(file_path)

    elif extension == ".docx":
        return docx_extractor(file_path)

    elif extension in [".ppt", ".pptx"]:
        slide_texts = ppt_extractor(file_path)
        text = "\n\n".join(slide_texts) if isinstance(slide_texts, list) else ""
        return {"text": text}

    elif extension in [".hwp", ".hwpx"]:
        return hwp_extractor(file_path)

    else:
        print("지원하지 않는 확장자")
        return {"text": ""}
