from pathlib import Path

from check_file import check_input_file
from convert_pdf import convert_docx_to_pdf
from pdf_to_images import convert_pdf_to_images


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

OUTPUT_DIR = BASE_DIR / "output"

PDF_DIR = OUTPUT_DIR / "pdf"
IMAGE_DIR = OUTPUT_DIR / "images"


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

    print("\n===== STEP 03 COMPLETE =====")

    for image_path in image_paths:
        print(image_path.name)


if __name__ == "__main__":
    main()