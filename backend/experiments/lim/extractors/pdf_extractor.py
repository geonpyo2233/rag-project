import pdfplumber
from pdf2image import convert_from_path
from paddleocr import PaddleOCR
import json

pdf_path = '/Users/imgeonpyo/rag-project/backend/experiments/lim/data/raw_data/[교안_강의]11_보안위헙관리통제 part1_02회차.pdf'
threshold = 50
output = 'output.json'

ocr = PaddleOCR(use_angle_cls = True, lang = 'korean')

def get_text_by_ocr(image):
    result = ocr.ocr(image, cls=True)

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
        text = page.extract_text or ""

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