import pdfplumber
from pdf2image import convert_from_path
from paddleocr import PaddleOCR
import json
import numpy as np

pdf_path = r"C:\Users\2class_13\RAG_project\rag-project\backend\experiments\lim\data\test.pdf"
threshold = 50
output = r'C:\Users\2class_13\RAG_project\rag-project\backend\experiments\lim\data\ocr_output\test\output.json'

ocr = PaddleOCR(use_angle_cls = True, lang = 'korean')

def get_text_by_ocr(image):
    image_np = np.array(image)
    result = ocr.ocr(image_np, cls=True)

    texts = []
    for block in result:
        if block :
            for line in block:
                texts.append(line[1][0])
    return '\n'.join(texts)

images = convert_from_path(pdf_path)
results = []

with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""

        if len(text.strip()) >= threshold:
            method = 'text'
            content = text.strip()
        else :
            method = 'ocr'
            content = get_text_by_ocr(images[i])

        results.append({
            'page' : i+1,
            'method' : method,
            'content' : content
        })

        print(f'페이지{i+1}완료 ({method})')

with open(output, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f'완료 {output} 저장')