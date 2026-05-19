def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100
):
    """
    긴 텍스트를 일정한 크기의 chunk로 나누는 함수
    """

    if not text.strip():
        return []

    chunks = []

    start = 0
    text_length = len(text)

    while start < text_length:

        end = start + chunk_size

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start = end - overlap

    return chunks


def save_chunks(chunks, output_path):
    """
    chunk 결과 txt 저장
    """

    lines = []

    for index, chunk in enumerate(chunks, start=1):

        lines.append(f"\n===== CHUNK {index} START =====")

        lines.append(chunk)

        lines.append(f"===== CHUNK {index} END =====\n")

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )

    return output_path