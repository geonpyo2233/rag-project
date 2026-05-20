from pathlib import Path
import json

import pdfplumber
from pdf2image import convert_from_path
from paddleocr import PaddleOCR
import numpy as np

from config import TEXT_OUTPUT_DIR, OUTPUT_DIR


# Lim 원본 방식 유지: PDF 이미지 OCR에 사용할 PaddleOCR 객체를 준비합니다.
ocr = PaddleOCR(lang="korean")


def get_text_by_ocr(image):
    image_np = np.array(image)
    result = ocr.ocr(image_np)

    texts = []
    for block in result:
        if block:
            for line in block:
                texts.append(line[1][0])

    return "\n".join(texts)


def extract(pdf_path, output_path, threshold=50):
    print(f"PDF 추출 시작: {pdf_path}")

    pdf_path = Path(pdf_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Lim 원본 방식 유지: pdf2image로 PDF 페이지를 이미지로 변환합니다.
    images = convert_from_path(pdf_path, dpi=400)

    results = []

    # Lim 원본 방식 유지: pdfplumber로 먼저 텍스트를 추출하고, 부족하면 OCR로 보완합니다.
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""

            if len(text.strip()) >= threshold:
                method = "text"
                content = text.strip()
            else:
                method = "ocr"
                content = get_text_by_ocr(images[i])

            results.append({
                "page": i + 1,
                "method": method,
                "content": content,
            })

            print(f"페이지 {i + 1} 완료 ({method})")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"PDF 추출 완료: {output_path}")
    return output_path


def pdf_extractor(file_path: Path):
    # FIX: mergeCode 파이프라인은 pdf_extractor(file_path)를 호출하므로,
    # Lim 원본 extract(pdf_path, output_path)를 감싸는 래퍼만 추가했습니다.
    file_path = Path(file_path)
    json_path = OUTPUT_DIR / "json" / f"{file_path.stem}_pdf_extract.json"
    extract(file_path, json_path)

    with open(json_path, encoding="utf-8") as f:
        pages = json.load(f)

    # FIX: mergeCode의 다른 extractor들과 맞추기 위해 최종 TXT도 output/text에 저장합니다.
    result_text = "\n\n".join(page["content"] for page in pages)
    result_path = TEXT_OUTPUT_DIR / f"{file_path.stem}_hybrid_extract.txt"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(result_text, encoding="utf-8")

    return {
        "file_name": file_path.name,
        "pages": pages,
        "text": result_text,
        "json_path": json_path,
        "text_path": result_path,
    }
