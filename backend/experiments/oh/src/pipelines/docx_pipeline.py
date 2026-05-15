from pathlib import Path

from extractors.docx_extractor import (
    load_docx,
    extract_paragraphs,
    extract_tables,
    extract_images_from_docx,
)
from ocr.paddle_ocr import run_ocr_on_images


def run_docx_hybrid_pipeline(docx_path: Path, output_dir: Path):
    """
    DOCX 하이브리드 추출 파이프라인

    1. 문단 직접 추출
    2. Word 표 직접 추출
    3. DOCX 내부 이미지 추출
    4. 이미지 OCR
    5. 전체 결과 txt 저장
    """
    print("\n===== DOCX HYBRID PIPELINE START =====")

    output_dir.mkdir(parents=True, exist_ok=True)

    image_output_dir = output_dir / "docx_images"
    text_output_dir = output_dir / "text"
    text_output_dir.mkdir(parents=True, exist_ok=True)

    document = load_docx(docx_path)

    all_texts = []

    print("\n[1] 문단 텍스트 직접 추출")
    all_texts.extend(extract_paragraphs(document))

    print("\n[2] Word 표 텍스트 직접 추출")
    all_texts.extend(extract_tables(document))

    print("\n[3] DOCX 내부 이미지 추출")
    image_paths = extract_images_from_docx(docx_path, image_output_dir)
    print(f"추출된 이미지 개수: {len(image_paths)}")

    print("\n[4] 이미지 OCR")
    image_ocr_texts = run_ocr_on_images(image_paths)
    all_texts.extend(image_ocr_texts)

    result_text = "\n".join(all_texts)

    result_path = text_output_dir / f"{docx_path.stem}_hybrid_extract.txt"
    result_path.write_text(result_text, encoding="utf-8")

    print("\n===== 저장 완료 =====")
    print(result_path)

    return result_path