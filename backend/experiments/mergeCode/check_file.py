# ==============================
# check_file.py
# ==============================

from pathlib import Path

from config import SUPPORTED_EXTENSIONS


def check_input_files(data_dir: Path):
    """
    data 폴더 안의 입력 파일을 확인하는 함수

    역할:
    1. data 폴더 존재 확인
    2. 파일 목록 조회
    3. 지원 확장자만 필터링
    4. 처리 가능한 파일 리스트 반환
    """

    print("\n===== STEP 01 : INPUT FILE CHECK =====")

    if not data_dir.exists():
        raise FileNotFoundError(
            f"data 폴더가 존재하지 않습니다:\n{data_dir}"
        )

    files = [
        file
        for file in data_dir.glob("*")
        if file.is_file()
    ]

    if not files:
        raise FileNotFoundError(
            f"data 폴더에 파일이 없습니다:\n{data_dir}"
        )

    supported_files = []
    unsupported_files = []

    for file in files:
        extension = file.suffix.lower()

        if extension in SUPPORTED_EXTENSIONS:
            supported_files.append(file)
        else:
            unsupported_files.append(file)

    print("\n발견된 파일 목록:")

    for idx, file in enumerate(files, start=1):
        print(f"{idx}. {file.name}")

    print(f"\n전체 파일 개수: {len(files)}")
    print(f"지원 가능 파일 개수: {len(supported_files)}")
    print(f"지원 불가 파일 개수: {len(unsupported_files)}")

    if unsupported_files:
        print("\n지원하지 않는 파일:")

        for file in unsupported_files:
            print(f"- {file.name}")

    if not supported_files:
        raise FileNotFoundError(
            "처리 가능한 지원 확장자 파일이 없습니다."
        )

    return supported_files