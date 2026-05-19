from pathlib import Path

from config import (
    DOCX_OCR_UPSCALE_ENABLED,
    DOCX_OCR_UPSCALE_FACTOR,
    OCR_LANGUAGE,
    OCR_USE_GPU,
)


# PaddleOCR 모델은 무겁기 때문에 import 시점에 바로 만들지 않는다.
# 실제 DOCX 이미지 OCR이 필요할 때 get_ocr()에서 한 번만 생성해서 재사용한다.
_ocr = None


def get_ocr():
    """PaddleOCR 인스턴스를 lazy init 방식으로 생성하고 재사용한다."""
    global _ocr

    if _ocr is None:
        from paddleocr import PaddleOCR

        _ocr = PaddleOCR(
            use_angle_cls=True,
            lang=OCR_LANGUAGE,
            use_gpu=OCR_USE_GPU,
            show_log=False,
        )

    return _ocr


def extract_text_items_from_ocr_result(result):
    """PaddleOCR 결과에서 텍스트, 신뢰도, 좌표를 꺼내 공통 dict 형태로 정리한다."""
    extracted_items = []

    if not result or not result[0]:
        return extracted_items

    for line in result[0]:
        box = line[0]
        text = line[1][0]
        score = line[1][1]

        if not text.strip():
            continue

        extracted_items.append({
            "text": text.strip(),
            "score": score,
            "box": box,
        })

    return extracted_items


def sort_ocr_texts_by_position(items):
    """OCR 라인을 위쪽에서 아래쪽, 같은 줄에서는 왼쪽에서 오른쪽 순서로 정렬한다."""
    sorted_items = sorted(
        items,
        key=lambda item: (
            item["box"][0][1],
            item["box"][0][0],
        ),
    )

    return [item["text"] for item in sorted_items]


def prepare_image_for_ocr(image_path: Path, output_dir: Path | None = None):
    """OCR 정확도 개선을 위해 RGB 원본을 유지한 채 설정 배율만큼 확대한다."""
    if not DOCX_OCR_UPSCALE_ENABLED or DOCX_OCR_UPSCALE_FACTOR <= 1:
        return image_path

    from PIL import Image

    if output_dir is None:
        output_dir = image_path.parent / "upscaled"

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{image_path.stem}_{DOCX_OCR_UPSCALE_FACTOR}x.png"

    image = Image.open(image_path).convert("RGB")
    resampling = getattr(Image, "Resampling", Image).BICUBIC
    resized = image.resize(
        (
            image.width * DOCX_OCR_UPSCALE_FACTOR,
            image.height * DOCX_OCR_UPSCALE_FACTOR,
        ),
        resampling,
    )
    resized.save(output_path)

    return output_path


def run_ocr_on_images(image_paths, preprocess_output_dir: Path | None = None):
    """DOCX에서 추출한 이미지 목록에 OCR을 수행하고 텍스트 블록 리스트를 반환한다."""
    if not image_paths:
        return []

    ocr = get_ocr()
    texts = []

    for image_index, image_path in enumerate(image_paths, start=1):
        image_path = Path(image_path)
        # 원본 이미지는 보존하고, OCR에는 업스케일된 복사본을 사용한다.
        ocr_image_path = prepare_image_for_ocr(image_path, preprocess_output_dir)

        print(f"OCR running: {image_path.name} -> {ocr_image_path.name}")
        texts.append(f"\n===== IMAGE OCR {image_index}: {image_path.name} =====")

        result = ocr.ocr(str(ocr_image_path))
        extracted_items = extract_text_items_from_ocr_result(result)
        sorted_texts = sort_ocr_texts_by_position(extracted_items)

        texts.append("\n".join(sorted_texts))

    return texts
