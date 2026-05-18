# ==============================
# document_pipeline.py
# ==============================

from pathlib import Path


def run_document_pipeline(file_path: Path):
    """
    문서 확장자에 따라
    적절한 파이프라인으로 분기하는 함수
    """

    extension = file_path.suffix.lower()

    print("\n==============================")
    print(f"파일 처리 시작: {file_path.name}")
    print(f"확장자: {extension}")
    print("==============================")

    # ==============================
    # DOCX
    # ==============================

    if extension == ".docx":
        print(".docx 실행")

    # ==============================
    # PDF
    # ==============================

    elif extension == ".pdf":
        print(".pdf 실행")

    # ==============================
    # PPTX
    # ==============================

    elif extension == ".pptx":
        print(".pptx 실행")

    # ==============================
    # HWPX
    # ==============================

    elif extension == ".hwpx":
        print(".hwpx 실행")

    
    # ==============================
    # 지원하지 않는 파일
    # ==============================

    else:
        print("지원하지 않는 확장자")