import pdfplumber
from pdf2image import convert_from_path
from paddleocr import PaddleOCR
import json
import numpy as np

# PaddleOCR은 매번 새로 로드하면 느리니까 한 번만 로드
ocr = PaddleOCR(use_angle_cls=True, lang='korean')


def get_text_by_ocr(image):
    # 이미지를 받아 OCR로 텍스트 추출
    image_np = np.array(image)
    result = ocr.ocr(image_np, cls=True)

    texts = []
    for block in result:
        if block:
            for line in block:
                texts.append(line[1][0])
    return '\n'.join(texts)


def extract(pdf_path, output_path, threshold=50):
    # PDF를 받아 텍스트를 추출하고 JSON으로 저장
    print(f'[추출 시작] {pdf_path}')

    # PDF를 이미지로 변환 (OCR 폴백용)
    images = convert_from_path(pdf_path, dpi=400, grayscale=True)
    results = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""

            if len(text.strip()) >= threshold:
                method = 'text'
                content = text.strip()
            else:
                method = 'ocr'
                content = get_text_by_ocr(images[i])

            results.append({
                'page'   : i + 1,
                'method' : method,
                'content': content
            })

            print(f'  페이지 {i+1} 완료 ({method})')

    # JSON 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f'[추출 완료] {output_path} 저장')
    return output_path