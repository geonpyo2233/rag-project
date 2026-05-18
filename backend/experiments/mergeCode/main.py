# ==============================
# main.py
# ==============================

from pathlib import Path

from check_file import check_input_files
from pipelines.document_pipeline import (
    run_document_pipeline
)

# 현재 프로젝트 기준 루트 폴더
# 예: mergeCode/
BASE_DIR = Path(__file__).resolve().parent.parent

# 입력 파일 폴더
# 예: mergeCode/data/
DATA_DIR = BASE_DIR / "mergeCode/data"


def main():
    """
    메인 실행 함수

    현재 단계에서는 check_file.py가
    정상적으로 data 폴더의 파일을 확인하는지만 테스트함
    """

    print("===== MERGE PIPELINE START =====")

    # data 폴더 안의 지원 가능한 파일 목록 확인
    selected_files = check_input_files(DATA_DIR)

    print("\n===== 처리 대상 파일 =====")

    for file_path in selected_files:
        run_document_pipeline(file_path)

    print("\n===== CHECK FILE TEST COMPLETE =====")


if __name__ == "__main__":
    main()

    