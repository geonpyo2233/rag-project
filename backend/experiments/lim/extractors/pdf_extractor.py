from pdf2image import convert_from_path
from paddleocr import PaddleOCR
import json
import os

# =========================
# 경로 설정
# =========================
base_dir   = "/Users/imgeonpyo/rag-project/backend/experiments/lim"
pdf_path   = f"{base_dir}/data/raw_data/[교안_강의]11_보안위헙관리통제 part1_02회차.pdf"
output_dir = f"{base_dir}/data/ocr_output"
image_dir  = f"{output_dir}/images"

os.makedirs(output_dir, exist_ok=True)
os.makedirs(image_dir,  exist_ok=True)

# =========================
# PDF → 이미지 변환 (10~15페이지만)
# =========================
pages = convert_from_path(pdf_path, dpi=300, first_page=10, last_page=15)

# =========================
# OCR 모델 생성
# =========================
ocr = PaddleOCR(
    lang="korean",
    use_textline_orientation=True,
    det_db_thresh=0.3,
    det_db_box_thresh=0.5
)

# =========================
# 결과 저장 리스트
# =========================
all_raw_results   = []  # 원본 (모든 텍스트 + score)
all_clean_results = []  # score 0.6 미만 + 빈줄 제거
all_documents     = []  # 청킹 입력용 (페이지 단위 텍스트)

# =========================
# 전체 페이지 OCR 실행
# =========================
for page_num, page in enumerate(pages, start=10):
    print(f"\n[{page_num}/15] OCR 시작")

    # 흑백 변환 후 저장
    image_path = f"{image_dir}/page_{page_num:03d}.png"
    page.convert("L").save(image_path, "PNG")

    # OCR 실행
    result = ocr.predict(image_path)
    texts  = result[0]["rec_texts"]
    scores = result[0]["rec_scores"]

    # 원본 수집
    page_raw = []
    for text, score in zip(texts, scores):
        page_raw.append({
            "page":  page_num,
            "text":  text,
            "score": round(float(score), 4)
        })
    all_raw_results.extend(page_raw)

    # clean 수집 (빈줄 + score 0.6 미만 제거)
    page_clean = [
        item for item in page_raw
        if item["text"].strip() != "" and item["score"] >= 0.6
    ]
    all_clean_results.extend(page_clean)

    # Document 수집 (페이지 단위로 텍스트 합치기)
    all_documents.append({
        "page":   page_num,
        "text":   "\n".join(item["text"] for item in page_clean),
        "source": pdf_path
    })

    print(f"[{page_num}/15] 완료")

# =========================
# JSON 저장
# =========================
files = {
    "ocr_raw.json":       all_raw_results,
    "ocr_clean.json":     all_clean_results,
    "ocr_documents.json": all_documents
}

for filename, data in files.items():
    path = f"{output_dir}/{filename}"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"저장 완료: {path}")

print("\n===== OCR 완료 (10~15페이지) =====")