from __future__ import annotations

"""
HWP/HWPX 파싱 유틸.

기능:
- 업로드 파일 저장
- direct text 추출
- 객체 이미지 추출
- HWPX 본문 순서(텍스트/객체) 기반 merged text 구성
"""

import imghdr
import re
import shutil
import shlex
import subprocess
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

import olefile

from app.config import settings

try:
    from hwp_extract.hwp import HWPExtractor
except Exception:  # pragma: no cover
    HWPExtractor = None


def save_upload(file_bytes: bytes, dst_path: Path) -> None:
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_bytes(file_bytes)


def extract_text_from_hwp(path: Path) -> str:
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

        # 2) fallback: Section 스트림
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
    ext = path.suffix.lower()
    if ext == ".hwp":
        return extract_text_from_hwp(path)
    if ext == ".hwpx":
        return extract_text_from_hwpx(path)
    return ""


def extract_embedded_images_with_hwp_extract(path: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ext = path.suffix.lower()

    # HWPX: BinData 직접 추출
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

    # HWP: 라이브러리 우선 추출
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

    image_paths = [p for p in out_dir.rglob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}]
    if image_paths:
        return sorted(image_paths)

    # fallback: CLI
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

    return sorted([p for p in out_dir.rglob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}])


def build_merged_text_in_order(
    source_path: Path,
    raw_text: str,
    image_paths: list[Path],
    ocr_by_image: dict[str, str],
) -> str:
    """본문 순서에 따라 텍스트와 객체 OCR을 인터리빙한 merged_text 생성.

    - HWPX: section XML을 순회해 텍스트/객체 순서를 최대한 반영
    - HWP: 구조 파싱 난이도로 인해 현재는 raw + object OCR 순서 fallback
    """
    ext = source_path.suffix.lower()

    # 이미지 경로 -> BIN 키 매핑 (예: BIN0001)
    bin_to_ocr: dict[str, str] = {}
    for img in image_paths:
        key = _extract_bin_key(img)
        if not key:
            continue
        text = ocr_by_image.get(str(img.resolve()), "").strip()
        if text:
            bin_to_ocr[key] = text

    # HWPX는 문서 순서 기반 인터리빙
    if ext == ".hwpx":
        sequence = _extract_hwpx_sequence(source_path)
        if sequence:
            merged_parts: list[str] = []
            used_bins: set[str] = set()
            for kind, value in sequence:
                if kind == "text":
                    t = value.strip()
                    if t:
                        merged_parts.append(t)
                elif kind == "object":
                    k = value.upper()
                    if k in bin_to_ocr:
                        merged_parts.append(bin_to_ocr[k])
                        used_bins.add(k)

            # 순서 파싱에서 못 잡힌 OCR은 뒤에 보충
            for k, txt in bin_to_ocr.items():
                if k not in used_bins:
                    merged_parts.append(txt)

            merged = "\n\n".join(p for p in merged_parts if p).strip()
            if merged:
                return merged

    # HWP는 Section 레코드 기반 순서 인터리빙
    if ext == ".hwp":
        sequence = _extract_hwp_sequence(source_path)
        if sequence:
            merged_parts: list[str] = []
            used_bins: set[str] = set()
            for kind, value in sequence:
                if kind == "text":
                    t = value.strip()
                    if t:
                        merged_parts.append(t)
                elif kind == "object":
                    k = value.upper()
                    if k in bin_to_ocr:
                        merged_parts.append(bin_to_ocr[k])
                        used_bins.add(k)

            # 순서 파싱에서 못 잡힌 OCR은 뒤에 보충
            for k, txt in bin_to_ocr.items():
                if k not in used_bins:
                    merged_parts.append(txt)

            merged = "\n\n".join(p for p in merged_parts if p).strip()
            if merged:
                return merged

    # HWP 혹은 HWPX 순서 파싱 실패 fallback
    all_ocr = []
    for img in image_paths:
        t = ocr_by_image.get(str(img.resolve()), "").strip()
        if t:
            all_ocr.append(t)
    return "\n\n".join([t for t in [raw_text.strip(), "\n\n".join(all_ocr).strip()] if t]).strip()


def clean_work_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def _extract_hwpx_sequence(path: Path) -> list[tuple[str, str]]:
    """HWPX section XML에서 (text/object) 순서를 추출한다.

    object는 BINxxxx 키로 반환한다.
    """
    sequence: list[tuple[str, str]] = []
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = sorted(
                n for n in zf.namelist()
                if n.lower().endswith(".xml") and ("contents/section" in n.lower() or "section" in n.lower())
            )
            for name in names:
                try:
                    root = ET.fromstring(zf.read(name))
                except Exception:
                    continue
                for elem in root.iter():
                    # 텍스트 토큰
                    if elem.text and elem.text.strip():
                        sequence.append(("text", elem.text.strip()))

                    # 객체(BIN) 토큰
                    for attr_val in elem.attrib.values():
                        for key in re.findall(r"BIN\d{4,}", str(attr_val), flags=re.IGNORECASE):
                            sequence.append(("object", key.upper()))
    except Exception:
        return []
    return sequence


def _extract_hwp_sequence(path: Path) -> list[tuple[str, str]]:
    """HWP BodyText/Section 레코드에서 텍스트/객체 순서를 추출한다.

    참고:
    - HWP 레코드 헤더(4바이트): tag(10bit), level(10bit), size(12bit)
    - size가 0xFFF면 다음 4바이트가 실제 size(extended)
    """
    sequence: list[tuple[str, str]] = []
    if not olefile.isOleFile(str(path)):
        return sequence

    try:
        with olefile.OleFileIO(str(path)) as ole:
            compressed = _is_hwp_body_compressed(ole)
            section_streams = [
                s for s in ole.listdir()
                if len(s) >= 2 and s[0] == "BodyText" and s[1].startswith("Section")
            ]
            section_streams.sort(key=lambda x: x[1])

            for stream_name in section_streams:
                try:
                    data = ole.openstream(stream_name).read()
                    if compressed:
                        try:
                            data = zlib.decompress(data, -15)  # raw deflate
                        except Exception:
                            # 압축 해제 실패 시 원본으로 진행
                            pass

                    sequence.extend(_parse_hwp_section_records(data))
                except Exception:
                    continue
    except Exception:
        return []

    return sequence


def _is_hwp_body_compressed(ole: olefile.OleFileIO) -> bool:
    """HWP FileHeader의 속성 비트에서 압축 여부를 읽는다."""
    try:
        header = ole.openstream("FileHeader").read()
        # signature(32) + version(4) + properties(4)
        if len(header) < 40:
            return False
        props = int.from_bytes(header[36:40], "little", signed=False)
        return bool(props & 0x01)
    except Exception:
        return False


def _parse_hwp_section_records(data: bytes) -> list[tuple[str, str]]:
    """Section 바이너리에서 순서 토큰(text/object)을 추출."""
    tokens: list[tuple[str, str]] = []
    pos = 0
    n = len(data)

    while pos + 4 <= n:
        header = int.from_bytes(data[pos:pos + 4], "little", signed=False)
        pos += 4

        tag_id = header & 0x3FF
        size = (header >> 20) & 0xFFF
        if size == 0xFFF:
            if pos + 4 > n:
                break
            size = int.from_bytes(data[pos:pos + 4], "little", signed=False)
            pos += 4

        if pos + size > n:
            break
        payload = data[pos:pos + size]
        pos += size

        # 1) 텍스트 레코드(주요: PARA_TEXT=67)
        if tag_id == 67 and payload:
            decoded = payload.decode("utf-16le", errors="ignore")
            cleaned = _clean_hwp_text(decoded)
            if cleaned:
                for line in cleaned.splitlines():
                    t = line.strip()
                    if t:
                        tokens.append(("text", t))

        # 2) 객체 참조(BINxxxx) 탐지: ascii + utf16 모두
        for key in _extract_bin_keys_from_bytes(payload):
            tokens.append(("object", key))

    return tokens


def _extract_bin_keys_from_bytes(payload: bytes) -> list[str]:
    """레코드 payload에서 BIN 키를 순서대로 추출."""
    found: list[tuple[int, str]] = []
    seen: set[tuple[int, str]] = set()

    # ascii BIN0001
    for m in re.finditer(rb"BIN\d{4,}", payload, flags=re.IGNORECASE):
        item = (m.start(), m.group(0).decode("ascii", errors="ignore").upper())
        if item not in seen:
            seen.add(item)
            found.append(item)

    # utf-16le B\0I\0N\00001...
    u16 = payload.decode("utf-16le", errors="ignore")
    for m in re.finditer(r"BIN\d{4,}", u16, flags=re.IGNORECASE):
        item = (m.start() * 2, m.group(0).upper())
        if item not in seen:
            seen.add(item)
            found.append(item)

    found.sort(key=lambda x: x[0])
    return [k for _, k in found]


def _extract_bin_key(path: Path) -> str | None:
    """파일명에서 BINxxxx 키 추출."""
    m = re.search(r"(BIN\d{4,})", path.stem, flags=re.IGNORECASE)
    if not m:
        return None
    return m.group(1).upper()


def _clean_hwp_text(text: str) -> str:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        meaningful = re.findall(r"[가-ힱA-Za-z0-9\s\.,;:!?\-·()<>「」『』\"'_/]", line)
        ratio = len(meaningful) / max(len(line), 1)
        if ratio < 0.55:
            continue
        bad = sum(1 for ch in line if ord(ch) < 9 or (13 < ord(ch) < 32))
        if bad > 0:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _detect_image_ext(data: bytes, safe_name: str) -> str:
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
