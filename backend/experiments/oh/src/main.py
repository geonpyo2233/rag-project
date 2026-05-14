from config import DOCX_PATH, PDF_PATH, MAX_PAGES
from extractor import convert_docx_to_pdf, extract_text_from_pdf


convert_docx_to_pdf(DOCX_PATH, PDF_PATH)

results = extract_text_from_pdf(PDF_PATH, MAX_PAGES)

print("\n===== 최종 추출 결과 =====")

for item in results:
    print(f"\n--- {item['page']}페이지 / 방식: {item['method']} ---")
    print(item["text"])