from pathlib import Path

from check_file import check_input_file
from pipelines.docx_pipeline import run_docx_hybrid_pipeline


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"


def main():
    print("===== OCR PIPELINE START =====")

    selected_file = check_input_file(DATA_DIR)

    result_path = run_docx_hybrid_pipeline(
        selected_file,
        OUTPUT_DIR
    )

    print("\n===== COMPLETE =====")
    print(f"최종 결과 파일: {result_path}")


if __name__ == "__main__":
    main()