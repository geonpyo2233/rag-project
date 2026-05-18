import json
from pathlib import Path


def save_document_json(
    file_name: str,
    document_text: str,
    chunks: list,
    output_path: Path
):
    """
    문서 처리 결과 JSON 저장
    """

    chunk_items = []

    for index, chunk in enumerate(chunks, start=1):

        chunk_items.append({
            "chunk_id": index,
            "text": chunk
        })

    data = {
        "file_name": file_name,
        "document_text": document_text,
        "chunks": chunk_items,
        "summary": "",
        "keywords": [],
        "category": ""
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    return output_path