import fitz
from docx2pdf import convert
from paddleocr import PaddleOCR
from config import DIRECT_TEXT_MIN_CHARS


ocr = PaddleOCR(lang="korean", use_angle_cls=True)


def convert_docx_to_pdf(docx_path, pdf_path):
    convert(docx_path, pdf_path)


def extract_direct_text(page):
    return page.get_text().strip()


def extract_ocr_text(page, page_num):
    image_path = f"../data/page_{page_num}.png"

    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    pix.save(image_path)

    result = ocr.ocr(image_path, cls=True)

    texts = []

    if result and result[0]:
        for line in result[0]:
            texts.append(line[1][0])

    return "\n".join(texts)


def extract_text_from_pdf(pdf_path, max_pages):
    doc = fitz.open(pdf_path)
    results = []

    for page_num in range(min(max_pages, len(doc))):
        page = doc[page_num]

        direct_text = extract_direct_text(page)

        print(f"\n[{page_num + 1}페이지]")
        print(f"직접 추출 길이: {len(direct_text)}")

        if len(direct_text) < DIRECT_TEXT_MIN_CHARS:
            print("텍스트 부족 → OCR 실행")
            final_text = extract_ocr_text(page, page_num + 1)
            method = "ocr"
        else:
            print("직접 추출 사용")
            final_text = direct_text
            method = "direct"

        results.append({
            "page": page_num + 1,
            "method": method,
            "text": final_text
        })

    return results