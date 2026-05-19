# src/ocr/image_preprocessor.py

from pathlib import Path
import cv2


def upscale_image_for_ocr(image_path: Path, output_dir: Path):
    """
    OCR용 이미지 확대만 수행
    표/굵은 글씨 이미지에서는 과한 전처리보다 확대만 하는 게 안정적
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    image = cv2.imread(str(image_path))

    if image is None:
        raise FileNotFoundError(f"이미지를 읽을 수 없습니다: {image_path}")

    upscaled = cv2.resize(
        image,
        None,
        fx=2,
        fy=2,
        interpolation=cv2.INTER_CUBIC
    )

    output_path = output_dir / f"{image_path.stem}_upscaled.png"
    cv2.imwrite(str(output_path), upscaled)

    return output_path