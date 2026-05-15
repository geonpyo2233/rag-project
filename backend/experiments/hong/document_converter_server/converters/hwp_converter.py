from __future__ import annotations

import multiprocessing as mp
import struct
import traceback
import zlib
from pathlib import Path
from queue import Empty
from typing import Any

import olefile

from config import HWP_TIMEOUT_SECONDS, IMAGE_OUTPUT_DIR, PDF_OUTPUT_DIR, TEMP_DIR
from utils.file_utils import unique_path
from utils.logger import get_logger


logger = get_logger(__name__)


_MOJIBAKE_MARKERS = ("\ufffd", "\u5360", "\ud6c4", "\ud6c2", "\ucc59", "\uca09")


def _korean_text_score(text: str) -> int:
    """Score decoded text so legacy Korean encodings beat mojibake."""
    hangul = sum(1 for char in text if "\uac00" <= char <= "\ud7a3")
    ascii_letters = sum(1 for char in text if char.isascii() and char.isalnum())
    whitespace = sum(1 for char in text if char.isspace())
    # Characters commonly seen when Korean text is decoded with the wrong encoding.
    mojibake_markers = sum(text.count(marker) for marker in _MOJIBAKE_MARKERS)
    private_or_control = sum(
        1
        for char in text
        if (ord(char) < 32 and char not in "\n\r\t") or 0xE000 <= ord(char) <= 0xF8FF
    )
    return (hangul * 8) + ascii_letters + whitespace - (mojibake_markers * 20) - (private_or_control * 10)


def _is_text_usable(
    text: str,
    min_chars: int = 30,
    min_hangul_ratio: float = 0.03,
    max_replacement_ratio: float = 0.02,
) -> bool:
    stripped = text.strip()
    if len(stripped) < min_chars:
        return False

    total_non_space = max(1, sum(1 for char in stripped if not char.isspace()))
    hangul_count = sum(1 for char in stripped if "\uac00" <= char <= "\ud7a3")
    replacement_count = stripped.count("\ufffd")

    hangul_ratio = hangul_count / total_non_space
    replacement_ratio = replacement_count / total_non_space
    return hangul_ratio >= min_hangul_ratio and replacement_ratio <= max_replacement_ratio


def _read_hwp_export_text(path: Path) -> str:
    """Read Hancom text export with legacy Korean encoding fallback."""
    raw = path.read_bytes()
    if not raw:
        return ""

    candidates: list[tuple[str, str]] = []
    for encoding in ("utf-16", "utf-16-le", "utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            candidates.append((encoding, raw.decode(encoding).strip()))
        except UnicodeDecodeError:
            continue

    if not candidates:
        return raw.decode("cp949", errors="replace").strip()

    encoding, text = max(candidates, key=lambda item: _korean_text_score(item[1]))
    logger.info("Read HWP exported text using encoding=%s, chars=%s", encoding, len(text))
    return text


def _try_register_security_module(hwp: Any) -> None:
    """Register Hancom file path security module when it is available."""
    try:
        hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
    except Exception:
        # Some installations do not have the module registered. Conversion can still
        # work in trusted server environments, so keep this non-fatal.
        pass


def _hide_hwp_window(hwp: Any) -> None:
    try:
        hwp.XHwpWindows.Item(0).Visible = False
    except Exception:
        pass


def _quit_hwp(hwp: Any | None) -> None:
    if hwp is None:
        return
    try:
        hwp.Quit()
    except Exception:
        pass


def _hwp_to_pdf_worker(source: str, output: str, queue: mp.Queue) -> None:
    hwp = None
    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        source_path = Path(source).resolve()
        output_path = Path(output).resolve()

        if not source_path.exists():
            raise FileNotFoundError(f"HWP 파일을 찾을 수 없습니다: {source_path}")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        hwp = win32com.client.gencache.EnsureDispatch("HWPFrame.HwpObject")
        _try_register_security_module(hwp)
        _hide_hwp_window(hwp)

        opened = hwp.Open(str(source_path))
        if opened is False:
            raise RuntimeError("한컴오피스에서 HWP 파일을 열지 못했습니다.")

        saved = hwp.SaveAs(str(output_path), "PDF")
        if saved is False:
            raise RuntimeError("한컴오피스 PDF 저장 명령이 실패했습니다.")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("PDF 파일이 생성되지 않았거나 비어 있습니다.")

        queue.put({"ok": True, "output": str(output_path)})
    except Exception as exc:
        queue.put(
            {
                "ok": False,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
    finally:
        _quit_hwp(hwp)
        try:
            import pythoncom

            pythoncom.CoUninitialize()
        except Exception:
            pass


def _hwp_to_text_worker(source: str, output: str, queue: mp.Queue) -> None:
    hwp = None
    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        source_path = Path(source).resolve()
        output_path = Path(output).resolve()

        if not source_path.exists():
            raise FileNotFoundError(f"HWP file not found: {source_path}")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        hwp = win32com.client.gencache.EnsureDispatch("HWPFrame.HwpObject")
        _try_register_security_module(hwp)
        _hide_hwp_window(hwp)

        opened = hwp.Open(str(source_path))
        if opened is False:
            raise RuntimeError("Hancom Office could not open the HWP file.")

        saved = hwp.SaveAs(str(output_path), "TEXT")
        if saved is False:
            saved = hwp.SaveAs(str(output_path), "TXT")
        if saved is False:
            raise RuntimeError("Hancom Office text export command failed.")

        if not output_path.exists():
            raise RuntimeError("Text export file was not created.")

        text = _read_hwp_export_text(output_path)

        queue.put({"ok": True, "text": text})
    except Exception as exc:
        queue.put(
            {
                "ok": False,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
    finally:
        _quit_hwp(hwp)
        try:
            import pythoncom

            pythoncom.CoUninitialize()
        except Exception:
            pass


def convert_hwp_to_pdf(
    source_path: Path,
    output_dir: Path = PDF_OUTPUT_DIR,
    timeout_seconds: int = HWP_TIMEOUT_SECONDS,
) -> Path:
    """Convert HWP to PDF through Hancom Office COM automation.

    The conversion runs in a child process so a hung COM automation session can be
    terminated after the configured timeout.
    """
    source_path = source_path.resolve()
    if source_path.suffix.lower() != ".hwp":
        raise ValueError("HWP 변환기는 .hwp 파일만 처리합니다.")
    if not source_path.exists():
        raise FileNotFoundError(f"HWP 파일을 찾을 수 없습니다: {source_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = unique_path(output_dir / f"{source_path.stem}.pdf")

    queue: mp.Queue = mp.Queue()
    process = mp.Process(
        target=_hwp_to_pdf_worker,
        args=(str(source_path), str(output_path), queue),
        daemon=True,
    )

    logger.info("Starting HWP to PDF conversion: %s", source_path)
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(5)
        logger.error("HWP conversion timed out after %s seconds: %s", timeout_seconds, source_path)
        raise TimeoutError(
            f"HWP 변환 시간이 {timeout_seconds}초를 초과했습니다. "
            "한컴오피스 COM 자동화가 응답하지 않을 수 있습니다."
        )

    try:
        result = queue.get_nowait()
    except Empty as exc:
        raise RuntimeError("HWP 변환 프로세스가 결과를 반환하지 않았습니다.") from exc

    if not result.get("ok"):
        logger.error("HWP conversion failed: %s\n%s", result.get("error"), result.get("traceback"))
        raise RuntimeError(f"HWP PDF 변환 실패: {result.get('error')}")

    converted_path = Path(result["output"])
    logger.info("HWP converted to PDF: %s", converted_path)
    return converted_path


# ---------------------------------------------------------------------------
# OLE-based HWP5 text extraction (no COM / no Hancom Office required)
# ---------------------------------------------------------------------------

_HWPTAG_BEGIN = 0x010  # HWP record tag base offset
_HWPTAG_PARA_TEXT = _HWPTAG_BEGIN + 51  # 67 = 0x43

# HWP inline control characters that should be stripped from paragraph text.
_HWP_CHAR_REPLACEMENTS: dict[int, str | None] = {
    0: None, 1: None, 2: None, 3: None, 4: None, 5: None, 6: None, 7: None,
    8: None, 9: "\t", 10: "\n", 11: None, 12: None, 13: "\n",
    14: None, 15: None, 16: None, 17: None, 18: None, 19: None, 20: None,
    21: None, 22: None, 23: None, 24: None, 25: None, 26: None, 27: None,
    28: None, 29: None, 30: None, 31: None,
}


def _iter_hwp_records(stream_data: bytes):
    """Yield (tag_id, level, size, data) tuples from a raw HWP body stream."""
    offset = 0
    while offset < len(stream_data):
        if offset + 4 > len(stream_data):
            break
        header = struct.unpack_from("<I", stream_data, offset)[0]
        tag_id = header & 0x3FF
        # level = (header >> 10) & 0x3FF  # not needed for text extraction
        size = (header >> 20) & 0xFFF
        offset += 4
        if size == 0xFFF:  # extended size
            if offset + 4 > len(stream_data):
                break
            size = struct.unpack_from("<I", stream_data, offset)[0]
            offset += 4
        data = stream_data[offset : offset + size]
        offset += size
        yield tag_id, size, data


def _decode_para_text(data: bytes) -> str:
    """Decode HWPTAG_PARA_TEXT payload into a Python string.

    The payload is a sequence of UTF-16 LE code-units.  Code-points 0-31 are
    HWP inline controls; some map to whitespace, the rest are discarded.  The
    extended control characters (1, 2, 3, 11, 12, etc.) occupy *multiple*
    UTF-16 code-units in the stream (an 8-code-unit or 16-code-unit inline
    object), so we skip over their payload accordingly.
    """
    chars: list[str] = []
    i = 0
    length = len(data) // 2
    while i < length:
        code = struct.unpack_from("<H", data, i * 2)[0]
        if code < 32:
            replacement = _HWP_CHAR_REPLACEMENTS.get(code)
            if replacement is not None:
                chars.append(replacement)
            # Extended inline objects take 8 WCHARs total (including the
            # control char itself).
            if code in (1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23):
                i += 8  # skip the inline object payload
            else:
                i += 1
        else:
            chars.append(chr(code))
            i += 1
    return "".join(chars)


def extract_hwp_text_ole(source_path: Path) -> str:
    """Extract text from an HWP5 file by parsing its OLE compound structure.

    This bypasses Hancom Office COM automation entirely.  It reads the
    ``BodyText/SectionN`` streams, decompresses them (HWP5 uses zlib on
    individual streams when the document header indicates compression), and
    iterates over HWP record tags to collect paragraph text.

    Returns the concatenated plain text, or raises on failure.
    """
    source_path = Path(source_path).resolve()
    if not olefile.isOleFile(str(source_path)):
        raise ValueError(f"Not a valid OLE (HWP5) file: {source_path}")

    ole = olefile.OleFileIO(str(source_path))
    try:
        # Check if the document body is compressed (FileHeader flags).
        compressed = False
        if ole.exists("FileHeader"):
            file_header = ole.openstream("FileHeader").read()
            if len(file_header) >= 40:
                flags = struct.unpack_from("<I", file_header, 36)[0]
                compressed = bool(flags & 0x01)

        # Collect BodyText/Section* streams.
        section_names = sorted(
            [s for s in ole.listdir() if len(s) == 2 and s[0] == "BodyText" and s[1].startswith("Section")],
            key=lambda s: int(s[1].replace("Section", "")) if s[1].replace("Section", "").isdigit() else 0,
        )

        if not section_names:
            raise RuntimeError("HWP file contains no BodyText sections.")

        paragraphs: list[str] = []
        for section_entry in section_names:
            raw = ole.openstream(section_entry).read()
            if compressed:
                try:
                    raw = zlib.decompress(raw, -15)
                except zlib.error:
                    # Try with default wbits as fallback.
                    raw = zlib.decompress(raw)

            for tag_id, _size, data in _iter_hwp_records(raw):
                if tag_id == _HWPTAG_PARA_TEXT and data:
                    para = _decode_para_text(data).strip()
                    if para:
                        paragraphs.append(para)

        text = "\n".join(paragraphs)
        logger.info(
            "OLE-based HWP text extraction got %s chars from %s sections: %s",
            len(text),
            len(section_names),
            source_path,
        )
        return text
    finally:
        ole.close()


# ---------------------------------------------------------------------------
# OLE-based HWP5 image detection
# ---------------------------------------------------------------------------

# HWP inline control code for GSO (Graphic / Shape Object)
_HWP_GSO_CONTROL = 11

# Common image file extensions stored inside BinData streams
_IMAGE_STREAM_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".wmf", ".emf"}


def _detect_image_extension(data: bytes) -> str | None:
    if len(data) < 8:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"BM"):
        return ".bmp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if data.startswith((b"II*\x00", b"MM\x00*")):
        return ".tif"
    if data.startswith(b"\x01\x00\x09\x00\x00\x03"):
        return ".wmf"
    if data.startswith(b"\x01\x00\x00\x00") and b" EMF" in data[:128]:
        return ".emf"
    return None


def _recover_image_like_bytes(raw: bytes) -> bytes:
    candidates = [raw]
    for mode in (-15, 15):
        try:
            candidates.append(zlib.decompress(raw, mode))
        except Exception:
            pass
    for candidate in candidates:
        if _detect_image_extension(candidate):
            return candidate
    return raw


def extract_hwp_bindata_images(
    source_path: Path,
    output_root: Path = IMAGE_OUTPUT_DIR,
) -> list[Path]:
    """Extract image-like BinData objects from HWP into output/images/<doc_stem>/objects."""
    source_path = Path(source_path).resolve()
    if not olefile.isOleFile(str(source_path)):
        return []

    output_dir = output_root / source_path.stem / "objects"
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []

    ole = olefile.OleFileIO(str(source_path))
    try:
        for entry in ole.listdir():
            if len(entry) < 2 or entry[0] != "BinData":
                continue

            stream_name = entry[-1]
            raw = ole.openstream(entry).read()
            data = _recover_image_like_bytes(raw)
            ext = _detect_image_extension(data)
            if not ext:
                continue

            base = Path(stream_name).stem or stream_name
            target = unique_path(output_dir / f"{base}{ext}")
            target.write_bytes(data)
            extracted.append(target)
    finally:
        ole.close()

    logger.info("Extracted %s BinData image objects from %s", len(extracted), source_path)
    return extracted


def detect_hwp_has_images(source_path: Path) -> bool:
    """Check whether an HWP5 file contains embedded images.

    Detection uses two complementary heuristics:

    1. **BinData streams**: HWP stores binary attachments (images, OLE objects)
       under the ``BinData/`` storage.  If any stream name ends with a known
       image extension, the document very likely contains images.
    2. **Inline GSO controls**: ``HWPTAG_PARA_TEXT`` payloads include inline
       control code 11 (GSO = Graphic/Shape Object) whenever an image or
       drawing object is placed inside a paragraph.  Scanning BodyText for
       this control is a reliable indicator.

    Returns ``True`` if either heuristic fires, ``False`` otherwise.
    If the file is not a valid OLE file, returns ``False`` conservatively.
    """
    source_path = Path(source_path).resolve()
    if not olefile.isOleFile(str(source_path)):
        logger.debug("detect_hwp_has_images: not an OLE file, returning False: %s", source_path)
        return False

    ole = olefile.OleFileIO(str(source_path))
    try:
        # --- Heuristic 1: BinData streams with image extensions ---------------
        for entry in ole.listdir():
            if len(entry) >= 2 and entry[0] == "BinData":
                stream_name = entry[-1].lower()
                for ext in _IMAGE_STREAM_EXTENSIONS:
                    if stream_name.endswith(ext):
                        logger.info(
                            "detect_hwp_has_images: found image BinData stream '%s' in %s",
                            "/".join(entry),
                            source_path,
                        )
                        return True

        # --- Heuristic 2: inline GSO controls in BodyText ---------------------
        compressed = False
        if ole.exists("FileHeader"):
            file_header = ole.openstream("FileHeader").read()
            if len(file_header) >= 40:
                flags = struct.unpack_from("<I", file_header, 36)[0]
                compressed = bool(flags & 0x01)

        section_names = [
            s for s in ole.listdir()
            if len(s) == 2 and s[0] == "BodyText" and s[1].startswith("Section")
        ]

        for section_entry in section_names:
            raw = ole.openstream(section_entry).read()
            if compressed:
                try:
                    raw = zlib.decompress(raw, -15)
                except zlib.error:
                    try:
                        raw = zlib.decompress(raw)
                    except zlib.error:
                        continue

            for tag_id, _size, data in _iter_hwp_records(raw):
                if tag_id == _HWPTAG_PARA_TEXT and data:
                    # Scan UTF-16 LE code-units for GSO control (code 11)
                    for j in range(0, len(data) - 1, 2):
                        code = struct.unpack_from("<H", data, j)[0]
                        if code == _HWP_GSO_CONTROL:
                            logger.info(
                                "detect_hwp_has_images: found inline GSO control in %s",
                                source_path,
                            )
                            return True

        logger.info("detect_hwp_has_images: no images detected in %s", source_path)
        return False
    except Exception as exc:
        logger.warning("detect_hwp_has_images: error during detection (%s), returning False", exc)
        return False
    finally:
        ole.close()


# ---------------------------------------------------------------------------
# Public API – extract_hwp_text (COM → OLE fallback)
# ---------------------------------------------------------------------------

def extract_hwp_text(
    source_path: Path,
    timeout_seconds: int = HWP_TIMEOUT_SECONDS,
) -> str:
    """Try direct HWP text extraction through OLE first, then COM fallback.

    Extraction order:
    1. OLE compound-file parsing (``olefile`` + ``zlib``).
    2. Hancom COM ``SaveAs(... , "TEXT")`` via a child process (only when needed).
    3. If both fail, raise so the caller can fall back to PDF/OCR.
    """
    source_path = source_path.resolve()
    if source_path.suffix.lower() != ".hwp":
        raise ValueError("HWP text extraction only supports .hwp files.")
    if not source_path.exists():
        raise FileNotFoundError(f"HWP file not found: {source_path}")

    # --- Stage 1: OLE structure parsing --------------------------------------
    ole_error: str | None = None
    ole_text: str = ""
    try:
        candidate = extract_hwp_text_ole(source_path).strip()
        if _is_text_usable(candidate):
            logger.info(
                "[Stage 1/2] OLE extraction succeeded: %s chars from %s",
                len(candidate),
                source_path,
            )
            return candidate
        ole_text = candidate
        ole_error = (
            f"OLE extraction quality below threshold (chars={len(candidate)})"
            if candidate
            else "OLE extraction returned empty text"
        )
        logger.warning("[Stage 1/2] %s", ole_error)
    except Exception as exc:
        ole_error = str(exc)
        logger.warning("[Stage 1/2] OLE extraction failed: %s", ole_error)

    # --- Stage 2: Hancom COM --------------------------------------------------
    com_error: str | None = None
    try:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        output_path = TEMP_DIR / f"{source_path.stem}_direct_text.txt"

        queue: mp.Queue = mp.Queue()
        process = mp.Process(
            target=_hwp_to_text_worker,
            args=(str(source_path), str(output_path), queue),
            daemon=True,
        )

        com_timeout_seconds = min(timeout_seconds, 40)
        logger.info(
            "[Stage 2/2] Starting COM-based HWP text extraction (timeout=%ss): %s",
            com_timeout_seconds,
            source_path,
        )
        process.start()
        process.join(com_timeout_seconds)

        if process.is_alive():
            process.terminate()
            process.join(5)
            com_error = f"COM extraction timed out after {com_timeout_seconds}s"
            logger.warning("HWP COM text extraction timed out: %s", source_path)
        else:
            try:
                result = queue.get_nowait()
            except Empty:
                com_error = "COM process returned no result"
                result = None

            if result and result.get("ok"):
                text = str(result.get("text") or "").strip()
                if _is_text_usable(text):
                    logger.info(
                        "[Stage 2/2] COM extraction succeeded: %s chars from %s",
                        len(text),
                        source_path,
                    )
                    return text
                com_error = (
                    f"COM extraction quality below threshold (chars={len(text)})"
                    if text
                    else "COM extraction returned empty text"
                )
            elif result:
                com_error = result.get("error", "unknown COM error")

    except Exception as exc:
        com_error = str(exc)

    logger.warning("[Stage 2/2] COM extraction failed: %s", com_error)

    if ole_text:
        logger.warning("Using low-quality OLE text as last direct-text candidate.")
        return ole_text

    # --- Both stages failed ---------------------------------------------------
    raise RuntimeError(
        f"HWP direct text extraction failed.\n"
        f"  OLE error: {ole_error}\n"
        f"  COM error: {com_error}"
    )
