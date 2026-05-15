# PDF 파일을 이미지로 변환해주는 라이브러리
from pdf2image import convert_from_path
# OCR종류 라이브러리
from paddleocr import PaddleOCR
# json 읽기 쓰기
import json
# 폴더 생성용
import os

# OCR할 PDF 주소
pdf_path   = r"C:\Users\2class_13\RAG_project\rag-project\backend\experiments\lim\data\test.pdf"
# OCR결과를 저장할 JSON 주소
output_dir = r"C:\Users\2class_13\RAG_project\rag-project\backend\experiments\lim\data\ocr_output\test"
# output_dir에 들어갈 이미지
image_dir  = r"C:\Users\2class_13\RAG_project\rag-project\backend\experiments\lim\data\ocr_output\images\test" 

# 위에 설정한 주소들이 없을 경우 생성 (exist_ok=True > 폴더가 있음 넘어가라)
os.makedirs(output_dir, exist_ok=True)
os.makedirs(image_dir,  exist_ok=True)

# PDF 전체를 이미지로 변환해서 리스트에 저장
pages = convert_from_path(pdf_path, dpi=400)
print(f"총 {len(pages)}페이지 변환 완료")

# PaddleOCR 객체 생성
ocr = PaddleOCR(
    lang="korean",                  # 한국어 인식 모드로 설정
    use_textline_orientation=True,  # 텍스트 방향 자동 감지
    det_db_thresh=0.2,              # 이미지에서 텍스트 영역을 감지하는 민감도
    det_db_box_thresh=0.3
)

all_raw_results   = []  # 원본 (모든 텍스트 + score)
all_clean_results = []  # score 0.5 미만 + 빈줄 제거
all_documents     = []  # 청킹 입력용 (페이지 단위 텍스트)

# pages리스트를 처음부터 끝까지 하나씩 꺼낸다
for page_num, page in enumerate(pages, start=1):
    print(f"\n[{page_num}/{len(pages)}] OCR 시작")

    # 저장할 이미지 파일경로 생성
    image_path = os.path.join(image_dir, f"page_{page_num:03d}.png")
    # 이미지를 흑백으로 변환해서 저장
    page.convert("L").save(image_path, "PNG")

    # 저장한 이미지를 OCR로 읽는다
    result = ocr.ocr(image_path, cls=True)

    # result[0]이 None이면 인식된 텍스트 없음 → 빈 리스트로 처리
    if not result or result[0] is None:
        print(f"[{page_num}] 인식된 텍스트 없음, 건너뜀")
        all_documents.append({
            "page":   page_num,
            "text":   "",
            "source": pdf_path
        })
        continue

    # result 구조: [[[박스좌표], (텍스트, 신뢰도)], ...]
    texts  = [line[1][0] for line in result[0]]  # 텍스트
    scores = [line[1][1] for line in result[0]]  # 신뢰도(score)

    # 원본 수집 (모든 텍스트)
    page_raw = []
    for text, score in zip(texts, scores):
        page_raw.append({
            "page":  page_num,
            "text":  text,
            "score": round(float(score), 4)
        })
    all_raw_results.extend(page_raw)

    # clean 수집 (빈줄만 제거, score 조건 없음 → 전체 텍스트 추출)
    page_clean = [
        item for item in page_raw
        if item["text"].strip() != ""
    ]
    all_clean_results.extend(page_clean)

    # Document 수집 (페이지 단위로 텍스트 합치기)
    all_documents.append({
        "page":   page_num,
        "text":   "\n".join(item["text"] for item in page_clean),
        "source": pdf_path
    })

    # 페이지별 추출 텍스트 길이 출력 (확인용)
    total_text = "\n".join(item["text"] for item in page_clean)
    print(f"[{page_num}/{len(pages)}] 완료 | 추출 텍스트: {len(total_text)}자")

# json 저장
files = {
    "ocr_raw.json":       all_raw_results,
    "ocr_clean.json":     all_clean_results,
    "ocr_documents.json": all_documents
}

for filename, data in files.items():
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"저장 완료: {path}")

print("\n===== OCR 완료 =====")



for text, score in zip(texts, scores):
    print(f"score: {score:.4f} | text: {text}")  # 추가
    page_raw.append({
        "page":  page_num,
        "text":  text,
        "score": round(float(score), 4)
    })