from pathlib import Path

from config import DIRECT_TEXT_MIN_CHARS, PDF_RENDER_SCALE, TEXT_OUTPUT_DIR
from extractors.hwp_ext.hwp_converter import (
    convert_hwp_to_pdf,
    extract_hwp_bindata_images,
    extract_hwp_text,
)
from extractors.hwp_ext.hwpx_parser import parse_hwpx_text
from extractors.pdf_ext.pdf_converter import render_pdf_to_images
def run_paddle_ocr_on_images(image_paths):
    """이미지 경로 목록에 PaddleOCR을 실행하고 {'text': 전체텍스트} 형태로 반환한다."""
    if not image_paths:
        return {"text": ""}
    try:
        from paddleocr import PaddleOCR
        import numpy as np
        from PIL import Image as _Image
        _ocr = PaddleOCR(lang="korean", use_angle_cls=True, show_log=False)
        texts = []
        for img_path in image_paths:
            img_np = np.array(_Image.open(img_path).convert("RGB"))
            result = _ocr.ocr(img_np)
            for block in (result or []):
                if block:
                    for line in block:
                        texts.append(line[1][0])
        return {"text": "\n".join(texts)}
    except Exception as e:
        return {"text": "", "error": str(e)}


def normalize_extracted_text(text: str):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def _text_is_enough(text: str, threshold: int = DIRECT_TEXT_MIN_CHARS):
    return len(text.strip()) >= threshold


def _run_hwp_pdf_ocr_fallback(file_path: Path):
    """Hong fallback route: HWP를 PDF로 변환한 뒤 렌더 이미지에 OCR을 수행한다."""
    pdf_path = convert_hwp_to_pdf(file_path)
    image_paths = render_pdf_to_images(pdf_path, scale=PDF_RENDER_SCALE)
    ocr_result = run_paddle_ocr_on_images(image_paths) if image_paths else None
    ocr_text = ocr_result.get("text", "") if ocr_result else ""

    return {
        "strategy": "hwp_to_pdf_ocr_fallback",
        "direct_text": "",
        "pdf_path": pdf_path,
        "image_paths": image_paths,
        "ocr_result": ocr_result,
        "ocr_texts": [ocr_text] if ocr_text else [],
        "direct_error": None,
    }


def hwp_extractor(file_path: Path):
    """Hong HWP/HWPX 추출 코드를 mergeCode 출력 형식으로 감싼 진입점."""
    file_path = Path(file_path).resolve()
    extension = file_path.suffix.lower()

    if extension == ".hwpx":
        strategy = "hwpx_xml_parser"
        direct_text = parse_hwpx_text(file_path)
        pdf_path = None
        image_paths = []
        ocr_texts = []
        ocr_result = None
        direct_error = None
    elif extension == ".hwp":
        direct_error = None
        try:
            # Hong 코드의 OLE 직접 추출을 먼저 사용하고, 필요 시 COM TEXT export로 fallback한다.
            direct_text = extract_hwp_text(file_path)
        except Exception as exc:
            direct_text = ""
            direct_error = str(exc)

        if _text_is_enough(direct_text):
            strategy = "hwp_direct_text_with_bindata_ocr"
            pdf_path = None

            # Hong 코드의 BinData 이미지 추출 로직을 그대로 사용한다.
            # OCR 실행은 Ye-rim님의 ocr_service.run_paddle_ocr_on_images를 사용한다.
            image_paths = extract_hwp_bindata_images(file_path)
            ocr_result = run_paddle_ocr_on_images(image_paths) if image_paths else None
            ocr_text = ocr_result.get("text", "") if ocr_result else ""
            ocr_texts = [ocr_text] if ocr_text else []
        else:
            # Hong 전체 라우팅과 동일한 fallback: 직접 추출 실패/부족 시 PDF 렌더 OCR로 처리한다.
            fallback_result = _run_hwp_pdf_ocr_fallback(file_path)
            strategy = fallback_result["strategy"]
            direct_text = fallback_result["direct_text"]
            pdf_path = fallback_result["pdf_path"]
            image_paths = fallback_result["image_paths"]
            ocr_result = fallback_result["ocr_result"]
            ocr_texts = fallback_result["ocr_texts"]
            direct_error = direct_error or "direct text below threshold"
    else:
        raise ValueError(f"HWP extractor는 .hwp/.hwpx만 지원합니다: {extension}")

    text_parts = []
    if direct_text:
        text_parts.append("[DIRECT_TEXT]\n" + normalize_extracted_text(direct_text))
    if ocr_texts:
        text_parts.append("[OCR_TEXT]\n" + normalize_extracted_text("\n".join(ocr_texts)))

    result_text = normalize_extracted_text("\n\n".join(text_parts))

    result_path = TEXT_OUTPUT_DIR / f"{file_path.stem}_hybrid_extract.txt"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(result_text, encoding="utf-8")

    return {
        "file_name": file_path.name,
        "strategy": strategy,
        "text": result_text,
        "direct_error": direct_error,
        "pdf_path": pdf_path,
        "image_paths": image_paths,
        "ocr_texts": ocr_texts,
        "ocr_result": ocr_result if extension == ".hwp" else None,
        "text_path": result_path,
    }
