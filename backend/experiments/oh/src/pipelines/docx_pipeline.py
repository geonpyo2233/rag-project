from pathlib import Path

from extractors.docx_extractor import (
    load_docx,
    extract_paragraphs,
    extract_tables,
    extract_images_from_docx,
)

from ocr.paddle_ocr import run_ocr_on_images

from rag.text_chunker import (
    chunk_text,
    save_chunks,
)

from writers.result_writer import (
    save_document_json
)


def run_docx_hybrid_pipeline(
    docx_path: Path,
    output_dir: Path
):
    """
    DOCX 하이브리드 추출 파이프라인
    """

    print("\n===== DOCX HYBRID PIPELINE START =====")

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    image_output_dir = output_dir / "docx_images"

    text_output_dir = output_dir / "text"

    chunk_output_dir = output_dir / "chunks"

    json_output_dir = output_dir / "json"

    text_output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    chunk_output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    json_output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    document = load_docx(docx_path)

    all_texts = []

    print("\n[1] 문단 텍스트 직접 추출")

    all_texts.extend(
        extract_paragraphs(document)
    )

    print("\n[2] Word 표 텍스트 직접 추출")

    all_texts.extend(
        extract_tables(document)
    )

    print("\n[3] DOCX 내부 이미지 추출")

    image_paths = extract_images_from_docx(
        docx_path,
        image_output_dir
    )

    print(f"추출된 이미지 개수: {len(image_paths)}")

    print("\n[4] 이미지 OCR")

    image_ocr_texts = run_ocr_on_images(
        image_paths
    )

    all_texts.extend(image_ocr_texts)

    result_text = "\n".join(all_texts)

    result_path = (
        text_output_dir /
        f"{docx_path.stem}_hybrid_extract.txt"
    )

    result_path.write_text(
        result_text,
        encoding="utf-8"
    )

    print("\n===== 전체 추출 텍스트 저장 완료 =====")

    print(result_path)

    print("\n[5] 텍스트 청킹")

    chunks = chunk_text(
        result_text,
        chunk_size=500,
        overlap=100
    )

    print(f"생성된 chunk 개수: {len(chunks)}")

    chunk_result_path = (
        chunk_output_dir /
        f"{docx_path.stem}_chunks.txt"
    )

    save_chunks(
        chunks,
        chunk_result_path
    )

    print("\n===== 청킹 결과 저장 완료 =====")

    print(chunk_result_path)

    print("\n[6] JSON 결과 저장")

    json_result_path = (
        json_output_dir /
        f"{docx_path.stem}_result.json"
    )

    save_document_json(
        file_name=docx_path.name,
        document_text=result_text,
        chunks=chunks,
        output_path=json_result_path
    )

    print("\n===== JSON 결과 저장 완료 =====")

    print(json_result_path)

    return result_path