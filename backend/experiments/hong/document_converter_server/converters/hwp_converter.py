from __future__ import annotations

import multiprocessing as mp
import traceback
from pathlib import Path
from queue import Empty
from typing import Any

from config import HWP_TIMEOUT_SECONDS, PDF_OUTPUT_DIR, TEMP_DIR
from utils.file_utils import unique_path
from utils.logger import get_logger


logger = get_logger(__name__)


def _korean_text_score(text: str) -> int:
    """Score decoded text so legacy Korean encodings beat mojibake."""
    hangul = sum(1 for char in text if "\uac00" <= char <= "\ud7a3")
    ascii_letters = sum(1 for char in text if char.isascii() and char.isalnum())
    whitespace = sum(1 for char in text if char.isspace())
    mojibake_markers = sum(text.count(marker) for marker in ("�", "?", "Ã", "Â", "ì", "µ"))
    private_or_control = sum(
        1
        for char in text
        if (ord(char) < 32 and char not in "\n\r\t") or 0xE000 <= ord(char) <= 0xF8FF
    )
    return (hangul * 8) + ascii_letters + whitespace - (mojibake_markers * 20) - (private_or_control * 10)


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


def extract_hwp_text(
    source_path: Path,
    timeout_seconds: int = HWP_TIMEOUT_SECONDS,
) -> str:
    """Try direct HWP text extraction through Hancom COM before OCR fallback."""
    source_path = source_path.resolve()
    if source_path.suffix.lower() != ".hwp":
        raise ValueError("HWP text extraction only supports .hwp files.")
    if not source_path.exists():
        raise FileNotFoundError(f"HWP file not found: {source_path}")

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    output_path = TEMP_DIR / f"{source_path.stem}_direct_text.txt"

    queue: mp.Queue = mp.Queue()
    process = mp.Process(
        target=_hwp_to_text_worker,
        args=(str(source_path), str(output_path), queue),
        daemon=True,
    )

    logger.info("Starting direct HWP text extraction: %s", source_path)
    process.start()
    process.join(timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(5)
        logger.warning("HWP direct text extraction timed out: %s", source_path)
        raise TimeoutError(f"HWP direct text extraction exceeded {timeout_seconds} seconds.")

    try:
        result = queue.get_nowait()
    except Empty as exc:
        raise RuntimeError("HWP text extraction process returned no result.") from exc

    if not result.get("ok"):
        logger.warning(
            "HWP direct text extraction failed: %s\n%s",
            result.get("error"),
            result.get("traceback"),
        )
        raise RuntimeError(f"HWP direct text extraction failed: {result.get('error')}")

    text = str(result.get("text") or "").strip()
    logger.info("Extracted %s direct text chars from HWP: %s", len(text), source_path)
    return text
