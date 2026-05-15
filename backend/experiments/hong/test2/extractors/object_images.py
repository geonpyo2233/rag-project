from __future__ import annotations

"""HWP/HWPX에서 객체 이미지(BinData)만 추출하는 모듈."""

import zipfile
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}


def _detect_image_extension(data: bytes) -> str | None:
    """매직바이트로 이미지 포맷을 판별한다(확장자 없을 때 보완용)."""
    if len(data) < 8:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"BM"):
        return ".bmp"
    return None


def extract_hwp_object_images(hwp_path: Path, objects_dir: Path) -> list[Path]:
    """HWP에서 객체 파일을 추출하고, 이미지 타입만 저장해 경로 목록을 반환한다."""
    from hwp_extract import HWPExtractor

    data = hwp_path.read_bytes()
    document = HWPExtractor(data=data)

    saved: list[Path] = []
    for idx, obj in enumerate(document.extract_files()):
        raw = obj.data
        ext = Path(obj.name).suffix.lower()
        if ext not in IMAGE_EXTENSIONS:
            ext = _detect_image_extension(raw) or ""
        if ext not in IMAGE_EXTENSIONS:
            continue

        stem = "".join(c for c in Path(obj.name).stem if c.isalnum() or c in ("_", "-")) or f"obj_{idx:04d}"
        target = objects_dir / f"{idx:04d}_{stem}{ext}"
        target.write_bytes(raw)
        saved.append(target)
    return saved


def extract_hwpx_object_images(hwpx_path: Path, objects_dir: Path) -> list[Path]:
    """HWPX(zip)에서 BinData 폴더의 이미지 파일만 추출한다."""
    saved: list[Path] = []
    with zipfile.ZipFile(hwpx_path, "r") as zf:
        for name in zf.namelist():
            if not name.lower().startswith("bindata/"):
                continue
            ext = Path(name).suffix.lower()
            if ext not in IMAGE_EXTENSIONS:
                continue
            data = zf.read(name)
            stem = "".join(c for c in Path(name).stem if c.isalnum() or c in ("_", "-")) or "obj"
            target = objects_dir / f"{len(saved):04d}_{stem}{ext}"
            target.write_bytes(data)
            saved.append(target)
    return saved


def enhance_object_images_for_ocr(
    image_paths: list[Path],
    enhanced_dir: Path,
    *,
    upscale: float = 2.0,
) -> list[Path]:
    """객체 원본 이미지를 OCR 친화적으로 보정한 사본을 만든다.

    처리:
    1) RGB 변환
    2) 업스케일(LANCZOS)
    3) 자동 대비 보정
    4) 약한 샤프닝
    5) PNG로 저장(재압축 손실 최소화)
    """
    enhanced_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []

    for src in image_paths:
        try:
            with Image.open(src) as im:
                rgb = im.convert("RGB")
                if upscale > 1.0:
                    new_w = max(1, int(round(rgb.width * upscale)))
                    new_h = max(1, int(round(rgb.height * upscale)))
                    rgb = rgb.resize((new_w, new_h), Image.Resampling.LANCZOS)
                rgb = ImageOps.autocontrast(rgb, cutoff=1)
                rgb = ImageEnhance.Contrast(rgb).enhance(1.2)
                rgb = rgb.filter(ImageFilter.UnsharpMask(radius=1.4, percent=140, threshold=2))

                target = enhanced_dir / f"{src.stem}_enh.png"
                rgb.save(target, format="PNG", optimize=True)
                outputs.append(target)
        except Exception:
            # 보정 실패 시 원본 사용
            outputs.append(src)

    return outputs
