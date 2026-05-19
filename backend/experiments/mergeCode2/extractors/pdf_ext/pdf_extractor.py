from pathlib import Path

import fitz


def pdf_extractor(file_path: Path):
    texts: list[str] = []
    with fitz.open(file_path) as doc:
        for page in doc:
            page_text = (page.get_text("text") or "").strip()
            if page_text:
                texts.append(page_text)

    result_text = "\n\n".join(texts).strip()
    return {
        "file_name": file_path.name,
        "text": result_text,
        "text_path": None,
    }
