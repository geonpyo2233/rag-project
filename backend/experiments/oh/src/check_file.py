from pathlib import Path


def check_input_file(data_dir: Path):
    print("\n===== STEP 01 : INPUT FILE CHECK =====")

    files = list(data_dir.glob("*"))

    if not files:
        raise FileNotFoundError(
            f"data 폴더에 파일이 없습니다.\n경로: {data_dir}"
        )

    print(f"\ndata 폴더 경로:")
    print(data_dir)

    print("\n발견된 파일 목록:")

    for idx, file in enumerate(files, start=1):
        print(f"{idx}. {file.name}")

    print(f"\n총 파일 개수: {len(files)}")

    selected_file = files[0]

    print("\n선택된 테스트 파일:")
    print(selected_file.name)

    print("\n전체 경로:")
    print(selected_file)

    return selected_file