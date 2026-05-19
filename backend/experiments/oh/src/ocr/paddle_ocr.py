# ==============================
# paddle_ocr.py
# ==============================

from pathlib import Path
from paddleocr import PaddleOCR
#from ocr.image_preprocessor import upscale_image_for_ocr


# ==============================
# PaddleOCR 모델 생성
# ==============================

# 한국어 OCR 모델 사용
#
# 현재 프로젝트 문서는 대부분 한글 중심이고,
# 중간에 영어 단어가 섞이는 구조임.
#
# lang="korean" 모델도 영어를 어느 정도 인식할 수 있음.
# 반대로 영어 OCR을 따로 돌리면 한글을 영어처럼 잘못 읽는 경우가 생겨
# OCR 결과가 더 지저분해질 수 있음.
ocr = PaddleOCR(
    use_angle_cls=True,
    lang="korean",
    use_gpu=False
)


def extract_text_items_from_ocr_result(result):
    """
    PaddleOCR 결과에서 텍스트, 신뢰도, 좌표를 함께 추출하는 함수

    여기서는 신뢰도(score)가 낮다고 바로 제거하지 않음.

    이유:
    - 영어 단어, 작은 글씨, 흐릿한 글씨는 score가 낮게 나올 수 있음
    - 지금 프로젝트는 LLM 요약/키워드 추출이 목적이므로
      최대한 텍스트를 보존한 뒤 LLM이 문맥을 파악하게 하는 전략을 사용

    반환 형태:
    [
        {
            "text": "인식된 텍스트",
            "score": 0.93,
            "box": 좌표정보
        }
    ]
    """

    extracted_items = []

    # OCR 결과가 비어 있으면 빈 리스트 반환
    if not result or not result[0]:
        return extracted_items

    # OCR 결과 한 줄씩 순회
    for line in result[0]:

        # OCR이 감지한 텍스트 영역 좌표
        box = line[0]

        # 실제 인식된 텍스트
        text = line[1][0]

        # OCR 신뢰도
        # 지금은 필터링하지 않고 JSON/텍스트 저장 시 참고용으로만 보관
        score = line[1][1]

        # 빈 문자열은 의미가 없으므로 제외
        if not text.strip():
            continue

        extracted_items.append({
            "text": text.strip(),
            "score": score,
            "box": box,
        })

    return extracted_items


def sort_ocr_texts_by_position(items):
    """
    OCR 결과를 좌표 기준으로 정렬하는 함수

    목적:
    이미지에서 사람이 읽는 순서와 비슷하게 정렬하기 위함

    정렬 기준:
    1. y좌표 기준 정렬
       - 위쪽에 있는 글자 먼저

    2. x좌표 기준 정렬
       - 같은 줄에서는 왼쪽 글자 먼저
    """

    sorted_items = sorted(
        items,
        key=lambda item: (
            item["box"][0][1],
            item["box"][0][0]
        )
    )

    texts = []

    for item in sorted_items:
        texts.append(item["text"])

    return texts


def run_ocr_on_images(image_paths):
    """
    이미지 목록에 PaddleOCR 실행

    처리 순서:

    1. 이미지 파일 하나씩 OCR 실행
    2. OCR 결과에서 텍스트, 신뢰도, 좌표 추출
    3. 좌표 기준으로 정렬
    4. 최종 텍스트 리스트에 저장
    """

    texts = []

    # 이미지 목록을 하나씩 순회
    for image_index, image_path in enumerate(image_paths, start=1):

        image_path = Path(image_path)

        print(f"OCR 실행 중: {image_path.name}")

        # 어떤 이미지에서 나온 OCR 결과인지 구분하기 위한 제목
        texts.append(
            f"\n===== IMAGE OCR {image_index}: {image_path.name} ====="
        )

        # ==============================
        # OCR 실행
        # ==============================

        result = ocr.ocr(str(image_path))

        # ==============================
        # OCR 결과 정리
        # ==============================

        extracted_items = extract_text_items_from_ocr_result(result)

        sorted_texts = sort_ocr_texts_by_position(extracted_items)

        # 정렬된 OCR 텍스트를 줄바꿈 기준으로 합쳐 저장
        texts.append("\n".join(sorted_texts))

    return texts