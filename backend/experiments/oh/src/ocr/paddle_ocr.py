from pathlib import Path
from paddleocr import PaddleOCR


ocr = PaddleOCR(lang="korean")


def run_ocr_on_images(image_paths):
    """이미지 목록에 PaddleOCR 실행"""
    texts = []

    for image_index, image_path in enumerate(image_paths, start=1):
        print(f"OCR 실행 중: {image_path.name}")

        texts.append(f"\n===== IMAGE OCR {image_index}: {image_path.name} =====")

        result = ocr.ocr(str(image_path))

        image_texts = []

        if result and result[0]:
            for line in result[0]:
                text = line[1][0]
                image_texts.append(text)

        texts.append("\n".join(image_texts))

    return texts