from pathlib import Path
from pdf2image import convert_from_path


POPPLER_PATH = r"C:\poppler\Library\bin"


def convert_pdf_to_images(pdf_path: Path, image_output_dir: Path):
    print("\n===== STEP 03 : PDF TO IMAGES =====")

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF 파일을 찾을 수 없습니다:\n{pdf_path}"
        )

    image_output_dir.mkdir(parents=True, exist_ok=True)

    images = convert_from_path(
        pdf_path=str(pdf_path),
        dpi=300,
        poppler_path=POPPLER_PATH
    )

    image_paths = []

    for index, image in enumerate(images, start=1):
        image_path = image_output_dir / f"{pdf_path.stem}_page_{index}.png"

        image.save(image_path, "PNG")

        image_paths.append(image_path)

        print(f"저장 완료: {image_path.name}")

    print(f"\n총 페이지 수: {len(image_paths)}")

    return image_paths