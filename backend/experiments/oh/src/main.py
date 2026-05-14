from pathlib import Path

from check_file import check_input_file
from convert_pdf import convert_docx_to_pdf
from pdf_to_images import convert_pdf_to_images
from run_ocr import run_ocr_on_images


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

PDF_DIR = OUTPUT_DIR / "pdf"
IMAGE_DIR = OUTPUT_DIR / "images"
TEXT_DIR = OUTPUT_DIR / "text"


def main():
    print("===== OCR PIPELINE START =====")

    selected_file = check_input_file(DATA_DIR)

    pdf_path = convert_docx_to_pdf(
        selected_file,
        PDF_DIR
    )

    image_paths = convert_pdf_to_images(
        pdf_path,
        IMAGE_DIR
    )

    result_path = run_ocr_on_images(
        image_paths,
        TEXT_DIR
    )

    print("\n===== STEP 04 COMPLETE =====")
    print(f"OCR 결과 파일: {result_path}")


if __name__ == "__main__":
    main()