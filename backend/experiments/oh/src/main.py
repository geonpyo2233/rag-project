from pathlib import Path

from check_file import check_input_file


BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"


def main():
    print("===== OCR PIPELINE START =====")

    selected_file = check_input_file(DATA_DIR)

    print("\n===== STEP 01 COMPLETE =====")
    print(f"테스트 파일: {selected_file.name}")


if __name__ == "__main__":
    main()