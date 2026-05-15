# PDF 파일을 이미지로 변환해주는 라이브러리
from pdf2image import convert_from_path
# OCR종류 라이브러리
from paddleocr import PaddleOCR
# json 읽기 쓰기
import json
# 폴더 생성용
import os

# 경로 시작
base_dir   = "/Users/imgeonpyo/rag-project/backend/experiments/lim"
# OCR할 PDF 주소
pdf_path   = f"{base_dir}/data/raw_data/[교안_강의]11_보안위헙관리통제 part1_02회차.pdf"
# OCR결과를 저장할 JSON 주소
output_dir = f"{base_dir}/data/ocr_output"
# output_dir에 들어갈 이미지
image_dir  = f"{output_dir}/images"

# 위에 설정한 주소들이 없을 경우 생성 (exist_ok=True > 폴더가 있음 넘어가라)
os.makedirs(output_dir, exist_ok=True)
os.makedirs(image_dir,  exist_ok=True)


# PDF 전체를 이미지로 변환해서 리스트에 저장
pages = convert_from_path(pdf_path, dpi=300)

# PaddleOCR 객체 생성
ocr = PaddleOCR(
    lang="korean", # 한국어 인식 모드로 설정
    use_textline_orientation=True, # 텍스트 방향 자동 감지
    det_db_thresh=0.3, # 이미지에서 텍스트 영역을 감지하는 민감도(0에 가까울 수록 많은 영역을 텍스트로 감지)
    det_db_box_thresh=0.5 
)

all_raw_results   = []  # 원본 (모든 텍스트 + score)
all_clean_results = []  # score 0.6 미만 + 빈줄 제거
all_documents     = []  # 청킹 입력용 (페이지 단위 텍스트)

# pages리스트를 처음부터 끝까지 하나씩 꺼낸다
for page_num, page in enumerate(pages, start=1):
    print(f"\n[{page_num}] OCR 시작")

    # 저장할 이미지 파일경로 생성 {:03d} > 숫자 세자리로 제목 맞추기
    image_path = f"{image_dir}/page_{page_num:03d}.png"
    # 이미지를 흑백으로 변환해서 저장
    page.convert("L").save(image_path, "PNG")

    # 저장한 이미지를 OC로 읽는다
    # predict()가 실제로 텍스트를 인식하는 함수
    result = ocr.predict(image_path)
    texts  = result[0]["rec_texts"] # 결과에서 인식되 텍스트 리스트
    scores = result[0]["rec_scores"] # 0~1사이의 점수 리스트

    # zip은 두 리스트를 짝찌어서 하나씩 꺼내준다
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

    print(f"[{page_num}] 완료")

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

print("\n===== OCR 완료 =====")