from pathlib import Path

from check_file import check_input_files
from pipelines.docx_pipeline import (
    run_docx_hybrid_pipeline
)


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"


def main():
    print("===== OCR PIPELINE START =====")

    selected_files = check_input_files(DATA_DIR)

    for selected_file in selected_files:
        print("\n====================================")
        print(f"처리 시작: {selected_file.name}")
        print("====================================")

        if selected_file.suffix.lower() == ".docx":

            result_path = run_docx_hybrid_pipeline(
                selected_file,
                OUTPUT_DIR
            )

            print(f"처리 완료: {result_path}")

        else:
            print(
                f"지원하지 않는 파일 형식이라 건너뜀: "
                f"{selected_file.name}"
            )


if __name__ == "__main__":
    main()