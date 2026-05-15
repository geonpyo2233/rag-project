from __future__ import annotations

"""test2 파이프라인 실행 모듈.

흐름:
1) data 폴더의 첫 번째 .hwp/.hwpx 파일 선택
2) direct text 추출 + 정리
3) 객체 이미지 추출
4) 객체 이미지 OCR
5) direct_text.txt / ocr_text.txt 저장
"""

import json
from pathlib import Path

from extractors.direct_text import clean_direct_text, extract_hwp_direct_text, extract_hwpx_direct_text
from extractors.object_images import (
    enhance_object_images_for_ocr,
    extract_hwp_object_images,
    extract_hwpx_object_images,
)
from ocr.engine import run_ocr_on_object_images


def run_pipeline(base_dir: Path, lang: str = "korean+en") -> dict:
    """전체 추출/OCR 파이프라인을 실행하고 결과 dict를 반환한다."""
    data_dir = base_dir / "data"
    out_dir = base_dir / "hwp_test2_out"
    objects_dir = out_dir / "objects"
    enhanced_dir = out_dir / "objects_enhanced"

    data_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    objects_dir.mkdir(parents=True, exist_ok=True)
    enhanced_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(p for p in data_dir.iterdir() if p.is_file() and p.suffix.lower() in {".hwp", ".hwpx"})
    if not files:
        raise FileNotFoundError(f"No .hwp/.hwpx file found in: {data_dir}")

    input_path = files[0].resolve()
    suffix = input_path.suffix.lower()

    if suffix == ".hwp":
        # HWP: OLE direct text + hwp_extract 객체 이미지
        direct_text = extract_hwp_direct_text(input_path)
        object_images = extract_hwp_object_images(input_path, objects_dir)
    else:
        # HWPX: XML direct text + zip BinData 이미지
        direct_text = extract_hwpx_direct_text(input_path)
        object_images = extract_hwpx_object_images(input_path, objects_dir)

    direct_text = clean_direct_text(direct_text)
    enhanced_images = enhance_object_images_for_ocr(object_images, enhanced_dir, upscale=2.0)
    ocr_result = run_ocr_on_object_images(enhanced_images, lang=lang)

    direct_text_path = out_dir / "direct_text.txt"
    ocr_text_path = out_dir / "ocr_text.txt"
    direct_text_path.write_text(direct_text, encoding="utf-8")
    ocr_text_path.write_text(ocr_result.get("merged_text", ""), encoding="utf-8")

    result = {
        "input": str(input_path),
        "output_dir": str(out_dir),
        "mode": "direct_text_plus_object_only_ocr_hybrid",
        "direct_text_path": str(direct_text_path.resolve()),
        "ocr_text_path": str(ocr_text_path.resolve()),
        "object_image_count": len(object_images),
        "object_images": [str(p.resolve()) for p in object_images],
        "enhanced_object_images": [str(p.resolve()) for p in enhanced_images],
        "ocr_result": ocr_result,
    }
    return result


def main() -> int:
    """CLI 진입점: test2 루트를 기준으로 파이프라인 실행 후 JSON 출력."""
    base_dir = Path(__file__).resolve().parents[1]
    result = run_pipeline(base_dir=base_dir, lang="korean+en")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
