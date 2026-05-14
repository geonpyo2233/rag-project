from pathlib import Path

from paddleocr import PaddleOCR


ocr = PaddleOCR(
    lang="korean"
)


def run_ocr_on_images(image_paths, text_output_dir: Path):
    print("\n===== STEP 04 : RUN PADDLE OCR =====")

    text_output_dir.mkdir(parents=True, exist_ok=True)

    all_text = []

    for image_path in image_paths:
        print(f"\nOCR 실행 중: {image_path.name}")

        # PaddleOCR v3 계열에서는 cls=True 제거
        result = ocr.ocr(str(image_path))

        page_texts = []

        if result and result[0]:
            for line in result[0]:
                text = line[1][0]
                score = line[1][1]

                page_texts.append(text)
                print(f"- {text} ({score:.2f})")

        all_text.append(f"\n===== {image_path.name} =====\n")
        all_text.append("\n".join(page_texts))

    result_text = "\n".join(all_text)

    result_path = text_output_dir / "ocr_result.txt"
    result_path.write_text(result_text, encoding="utf-8")

    print("\nOCR 결과 저장 완료")
    print(result_path)

    return result_path