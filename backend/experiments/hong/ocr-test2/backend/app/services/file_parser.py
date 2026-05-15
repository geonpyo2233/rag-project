from __future__ import annotations

"""
HWP/HWPX 파서 유틸.

기능:
- 업로드 파일 저장
- direct text 추출
- 객체 이미지 추출(hwp-extract import 우선, CLI fallback)
- 임시 작업 디렉터리 정리
"""

import imghdr
import re
import shutil
import shlex
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import olefile

from app.config import settings

try:
    from hwp_extract.hwp import HWPExtractor
except Exception:  # pragma: no cover
    HWPExtractor = None


def save_upload(file_bytes: bytes, dst_path: Path) -> None:
    """업로드 바이트를 지정 경로에 저장한다."""
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_bytes(file_bytes)


def extract_text_from_hwp(path: Path) -> str:
    """HWP(OLE)에서 direct text를 추출한다."""
    text_chunks: list[str] = []
    if not olefile.isOleFile(str(path)):
        return ""

    with olefile.OleFileIO(str(path)) as ole:
        # 1) 미리보기 텍스트 우선
        for stream_name in ole.listdir():
            joined = "/".join(stream_name)
            if "PrvText" not in joined:
                continue
            try:
                data = ole.openstream(stream_name).read()
                decoded = data.decode("utf-16le", errors="ignore").strip("\x00")
                cleaned = _clean_hwp_text(decoded)
                if cleaned:
                    text_chunks.append(cleaned)
            except Exception:
                continue

        # 2) 미리보기가 비면 Section fallback
        if not text_chunks:
            for stream_name in ole.listdir():
                joined = "/".join(stream_name)
                if "Section" not in joined:
                    continue
                try:
                    data = ole.openstream(stream_name).read()
                    decoded = data.decode("utf-16le", errors="ignore").strip("\x00")
                    cleaned = _clean_hwp_text(decoded)
                    if cleaned:
                        text_chunks.append(cleaned)
                except Exception:
                    continue

    return "\n".join(text_chunks).strip()


def extract_text_from_hwpx(path: Path) -> str:
    """HWPX(zip+xml)에서 텍스트 노드를 추출한다."""
    text_chunks: list[str] = []
    with zipfile.ZipFile(path, "r") as zf:
        for name in zf.namelist():
            if not name.endswith(".xml"):
                continue
            if "Contents" not in name and "section" not in name.lower():
                continue
            try:
                xml_bytes = zf.read(name)
                root = ET.fromstring(xml_bytes)
                for elem in root.iter():
                    if elem.text and elem.text.strip():
                        text_chunks.append(elem.text.strip())
            except Exception:
                continue
    return "\n".join(text_chunks).strip()


def extract_direct_text(path: Path) -> str:
    """확장자별 direct text 추출 분기."""
    ext = path.suffix.lower()
    if ext == ".hwp":
        return extract_text_from_hwp(path)
    if ext == ".hwpx":
        return extract_text_from_hwpx(path)
    return ""


def extract_embedded_images_with_hwp_extract(path: Path, out_dir: Path) -> list[Path]:
    """문서 내 객체 이미지를 추출해 이미지 경로 목록을 반환한다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = path.suffix.lower()

    # HWPX: BinData에서 직접 추출
    if ext == ".hwpx":
        try:
            with zipfile.ZipFile(path, "r") as zf:
                idx = 0
                for name in zf.namelist():
                    if not name.lower().startswith("bindata/"):
                        continue
                    raw = zf.read(name)
                    image_ext = _detect_image_ext(raw, Path(name).name)
                    if not image_ext:
                        continue
                    stem = Path(name).stem
                    target = out_dir / f"{idx:04d}_{stem}{image_ext}"
                    target.write_bytes(raw)
                    idx += 1
        except Exception:
            pass

    # HWP: 라이브러리 import 우선
    if HWPExtractor is not None and ext == ".hwp":
        try:
            data = path.read_bytes()
            doc = HWPExtractor(data=data, raise_pw_error=False)
            for idx, obj in enumerate(doc.extract_files()):
                safe_name = "".join(c for c in obj.name if c.isalnum() or c in ["_", "."])
                image_ext = _detect_image_ext(obj.data, safe_name)
                if not image_ext:
                    continue
                stem = Path(safe_name).stem if safe_name else f"obj_{idx}"
                target = out_dir / f"{path.stem}_{idx}_{stem}{image_ext}"
                target.write_bytes(obj.data)
        except Exception:
            pass

    image_paths: list[Path] = [p for p in out_dir.rglob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}]
    if image_paths:
        return image_paths

    # fallback: CLI 호출
    try:
        extra_args = shlex.split(settings.hwp_extract_args) if settings.hwp_extract_args.strip() else []
        cmd = [
            settings.hwp_extract_bin,
            str(path),
            "--extract-files",
            "--output-directory",
            str(out_dir),
            *extra_args,
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except Exception:
        return []

    return [p for p in out_dir.rglob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}]


def clean_work_dir(path: Path) -> None:
    """작업용 임시 디렉터리를 정리한다."""
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def _clean_hwp_text(text: str) -> str:
    """깨진 줄을 걸러내고 사람이 읽을 수 있는 줄만 남긴다."""
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        meaningful = re.findall(r"[가-힣A-Za-z0-9\s\.,;:!?\-·()<>《》“”\"'_/]", line)
        ratio = len(meaningful) / max(len(line), 1)
        if ratio < 0.55:
            continue
        bad = sum(1 for ch in line if ord(ch) < 9 or (13 < ord(ch) < 32))
        if bad > 0:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _detect_image_ext(data: bytes, safe_name: str) -> str:
    """바이너리/파일명 힌트를 이용해 이미지 확장자를 판별한다."""
    lower = safe_name.lower()
    for ext in [".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"]:
        if lower.endswith(ext):
            return ext
    detected = imghdr.what(None, h=data)
    if detected == "jpeg":
        return ".jpg"
    if detected in {"png", "bmp", "tiff", "webp"}:
        return f".{detected}"
    return ""
