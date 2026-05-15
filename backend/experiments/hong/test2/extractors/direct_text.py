from __future__ import annotations

"""HWP/HWPX 문서에서 direct text를 추출하는 모듈.

핵심 역할:
1) HWP(OLE/BodyText Section)에서 문단 텍스트를 직접 파싱
2) HWPX(zip+xml)에서 텍스트 노드를 수집
3) 추출 텍스트에 섞이는 깨짐 토큰(모지바케) 정리
"""

import re
import struct
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET

import olefile


_MOJIBAKE_RE = re.compile(
    r"(?:"
    r"汫ॣ|ྠĀ|20汫╣|"
    r"硔ȃ|㚤ȃ|棠ȃ|舄ȃ|窈ȃ|猌ȃ|䅌ȃ|硐ȃ|硘ȃ|"
    r"愸ȃ|破ȃ|瘌ȃ|穜ȃ|纨ȃ|峬ȃ|粀ȃ|"
    r"[\u3400-\u9FFF]ȃ"
    r")\s*"
)


def _iter_hwp_records(stream_data: bytes):
    """HWP BodyText 바이너리 스트림을 레코드 단위로 순회한다."""
    offset = 0
    while offset < len(stream_data):
        if offset + 4 > len(stream_data):
            break
        header = struct.unpack_from("<I", stream_data, offset)[0]
        tag_id = header & 0x3FF
        size = (header >> 20) & 0xFFF
        offset += 4
        if size == 0xFFF:
            if offset + 4 > len(stream_data):
                break
            size = struct.unpack_from("<I", stream_data, offset)[0]
            offset += 4
        data = stream_data[offset : offset + size]
        offset += size
        yield tag_id, data


def _decode_para_text(data: bytes) -> str:
    """HWPTAG_PARA_TEXT payload를 UTF-16 코드 단위로 해석해 일반 문자열로 변환한다."""
    chars: list[str] = []
    i = 0
    length = len(data) // 2
    while i < length:
        code = struct.unpack_from("<H", data, i * 2)[0]
        if code == 9:
            chars.append("\t")
            i += 1
            continue
        if code in (10, 13):
            chars.append("\n")
            i += 1
            continue
        if code < 32:
            if code in (1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23):
                i += 8
            else:
                i += 1
            continue
        chars.append(chr(code))
        i += 1
    return "".join(chars)


def extract_hwp_direct_text(hwp_path: Path) -> str:
    """HWP 파일에서 direct text를 추출한다.

    - OLE의 BodyText/Section* 스트림을 읽고
    - 압축(zlib raw) 해제 후
    - 문단 텍스트 태그(67)만 모아 텍스트로 반환한다.
    """
    if not olefile.isOleFile(str(hwp_path)):
        return ""
    texts: list[str] = []
    with olefile.OleFileIO(str(hwp_path)) as ole:
        for entry in ole.listdir():
            if len(entry) != 2 or entry[0] != "BodyText" or not entry[1].startswith("Section"):
                continue
            raw = ole.openstream(entry).read()
            try:
                data = zlib.decompress(raw, -15)
            except Exception:
                data = raw
            for tag_id, payload in _iter_hwp_records(data):
                if tag_id == 67:
                    line = _decode_para_text(payload).strip()
                    if line:
                        texts.append(line)
    return "\n".join(texts)


def extract_hwpx_direct_text(hwpx_path: Path) -> str:
    """HWPX(zip) 내부 XML을 순회하며 text node를 수집한다."""
    texts: list[str] = []
    with zipfile.ZipFile(hwpx_path, "r") as zf:
        xml_names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
        for name in xml_names:
            try:
                root = ET.fromstring(zf.read(name))
            except Exception:
                continue
            for elem in root.iter():
                if elem.text:
                    t = elem.text.strip()
                    if t:
                        texts.append(t)
    return "\n".join(texts)


def clean_direct_text(text: str) -> str:
    """direct text에 섞인 깨짐 토큰/과도한 공백/빈 줄을 정리한다."""
    cleaned = _MOJIBAKE_RE.sub("", text or "")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
