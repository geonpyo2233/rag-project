from __future__ import annotations

import argparse
import html
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from svglib.svglib import svg2rlg


def _ensure_rhwp_exists() -> str:
    rhwp_path = shutil.which("rhwp")
    if not rhwp_path:
        raise RuntimeError("rhwp CLI not found in PATH. Install rhwp first, then retry.")
    return rhwp_path


def _run(cmd: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(cmd, check=False, capture_output=True, text=False)


def _decode_output(data: bytes) -> str:
    if not data:
        return ""
    for enc in ("utf-8", "cp949", "euc-kr"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _supports_command(rhwp_bin: str, command_name: str) -> bool:
    probe = _run([rhwp_bin, "--help"])
    help_text = _decode_output(probe.stdout or b"") + "\n" + _decode_output(probe.stderr or b"")
    return command_name in help_text


def _export_svg_pages(rhwp_bin: str, input_path: Path, out_dir: Path) -> list[Path]:
    candidates = [
        [
            rhwp_bin,
            "export-svg",
            str(input_path),
            "-o",
            str(out_dir),
            "--embed-fonts=full",
            "--font-path",
            "C:\\Windows\\Fonts",
        ],
        [rhwp_bin, "export", "svg", str(input_path), "-o", str(out_dir)],
        [rhwp_bin, "svg", str(input_path), "-o", str(out_dir)],
    ]
    last_stdout = ""
    last_stderr = ""
    for cmd in candidates:
        result = _run(cmd)
        last_stdout = _decode_output(result.stdout or b"")
        last_stderr = _decode_output(result.stderr or b"")
        if result.returncode == 0:
            break
    else:
        raise RuntimeError(
            "rhwp SVG export command failed. Tried: export-svg, export svg, svg.\n"
            f"stdout:\n{last_stdout}\n"
            f"stderr:\n{last_stderr}"
        )

    pages = sorted(out_dir.glob("*.svg"))
    if not pages:
        raise RuntimeError("rhwp export-svg succeeded but no SVG files were generated.")
    return pages


def _export_png_pages(rhwp_bin: str, input_path: Path, out_dir: Path) -> list[Path]:
    cmd = [
        rhwp_bin,
        "export-png",
        str(input_path),
        "-o",
        str(out_dir),
        "--font-path",
        "C:\\Windows\\Fonts",
        "--scale",
        "2.0",
    ]
    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(
            "rhwp PNG export command failed.\n"
            f"stdout:\n{_decode_output(result.stdout or b'')}\n"
            f"stderr:\n{_decode_output(result.stderr or b'')}"
        )

    pages = sorted(list(out_dir.rglob("*.png")) + list(out_dir.rglob("*.PNG")))
    if not pages:
        raise RuntimeError("rhwp export-png succeeded but no PNG files were generated.")
    return pages


def _svg_pages_to_pdf(svg_pages: list[Path], output_pdf: Path) -> Path:
    first = svg2rlg(str(svg_pages[0]))
    if first is None:
        raise RuntimeError(f"Failed to parse SVG: {svg_pages[0]}")

    c = canvas.Canvas(str(output_pdf), pagesize=(float(first.width), float(first.height)))

    for svg_path in svg_pages:
        drawing = svg2rlg(str(svg_path))
        if drawing is None:
            raise RuntimeError(f"Failed to parse SVG: {svg_path}")

        width = float(drawing.width)
        height = float(drawing.height)
        c.setPageSize((width, height))
        renderPDF.draw(drawing, c, 0, 0)
        c.showPage()

    c.save()
    if not output_pdf.exists() or output_pdf.stat().st_size == 0:
        raise RuntimeError("PDF was not created or is empty.")
    return output_pdf


def _png_pages_to_pdf(png_pages: list[Path], output_pdf: Path) -> Path:
    first = ImageReader(str(png_pages[0]))
    fw, fh = first.getSize()
    c = canvas.Canvas(str(output_pdf), pagesize=(fw, fh))
    for png_path in png_pages:
        img = ImageReader(str(png_path))
        w, h = img.getSize()
        c.setPageSize((w, h))
        c.drawImage(img, 0, 0, width=w, height=h)
        c.showPage()
    c.save()
    if not output_pdf.exists() or output_pdf.stat().st_size == 0:
        raise RuntimeError("PDF was not created or is empty.")
    return output_pdf


def _to_px(value: str) -> float | None:
    raw = (value or "").strip()
    if not raw:
        return None
    unit = "".join(ch for ch in raw if ch.isalpha())
    num_str = raw[: len(raw) - len(unit)] if unit else raw
    try:
        num = float(num_str)
    except ValueError:
        return None
    unit = unit.lower()
    if unit in ("", "px"):
        return num
    if unit == "pt":
        return num * 96.0 / 72.0
    if unit == "mm":
        return num * 96.0 / 25.4
    if unit == "cm":
        return num * 96.0 / 2.54
    if unit == "in":
        return num * 96.0
    return None


def _svg_page_size_px(svg_path: Path) -> tuple[float, float]:
    root = ET.fromstring(svg_path.read_text(encoding="utf-8", errors="replace"))
    width = _to_px(root.attrib.get("width", ""))
    height = _to_px(root.attrib.get("height", ""))
    if width and height:
        return width, height

    view_box = root.attrib.get("viewBox", "").strip()
    if view_box:
        parts = view_box.replace(",", " ").split()
        if len(parts) == 4:
            try:
                return float(parts[2]), float(parts[3])
            except ValueError:
                pass

    drawing = svg2rlg(str(svg_path))
    if drawing is None:
        raise RuntimeError(f"Failed to parse SVG size: {svg_path}")
    return float(drawing.width), float(drawing.height)


def convert_hwp_to_pdf_with_rhwp(input_path: Path, output_path: Path) -> Path:
    input_path = input_path.resolve()
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if input_path.suffix.lower() not in {".hwp", ".hwpx"}:
        raise ValueError("Only .hwp/.hwpx files are supported.")

    rhwp_bin = _ensure_rhwp_exists()
    supports_svg = _supports_command(rhwp_bin, "export-svg")
    supports_png = _supports_command(rhwp_bin, "export-png")
    if not supports_svg and not supports_png:
        raise RuntimeError("This rhwp build does not expose export-svg or export-png command.")

    with tempfile.TemporaryDirectory(prefix="rhwp_svg_") as temp_dir:
        temp_path = Path(temp_dir)
        if supports_svg:
            try:
                svg_pages = _export_svg_pages(rhwp_bin, input_path, temp_path)
                return _svg_pages_to_pdf(svg_pages, output_path)
            except Exception:
                if not supports_png:
                    raise
        png_pages = _export_png_pages(rhwp_bin, input_path, temp_path)
        return _png_pages_to_pdf(png_pages, output_path)


async def convert_hwp_to_pdf_with_browser_print(input_path: Path, output_path: Path) -> Path:
    """Convert via rhwp PNG/SVG export + headless browser print-to-PDF."""
    from playwright.async_api import async_playwright

    input_path = input_path.resolve()
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if input_path.suffix.lower() not in {".hwp", ".hwpx"}:
        raise ValueError("Only .hwp/.hwpx files are supported.")

    rhwp_bin = _ensure_rhwp_exists()
    supports_png = _supports_command(rhwp_bin, "export-png")
    supports_svg = _supports_command(rhwp_bin, "export-svg")
    if not supports_png and not supports_svg:
        raise RuntimeError("This rhwp build does not expose export-png or export-svg command.")

    with tempfile.TemporaryDirectory(prefix="rhwp_svg_print_") as temp_dir:
        temp_path = Path(temp_dir)
        image_pages: list[Path]
        if supports_png:
            try:
                image_pages = _export_png_pages(rhwp_bin, input_path, temp_path)
            except Exception:
                if not supports_svg:
                    raise
                image_pages = _export_svg_pages(rhwp_bin, input_path, temp_path)
        else:
            image_pages = _export_svg_pages(rhwp_bin, input_path, temp_path)

        if image_pages[0].suffix.lower() == ".svg":
            first_w, first_h = _svg_page_size_px(image_pages[0])
        else:
            first_img = ImageReader(str(image_pages[0]))
            first_w, first_h = first_img.getSize()

        html_path = temp_path / "print.html"
        html_content = [
            "<!doctype html><html><head><meta charset='utf-8'>",
            "<style>",
            f"@page{{size:{first_w}px {first_h}px;margin:0;}}",
            "html,body{margin:0;padding:0;background:#fff;}",
            "body{width:max-content;}",
            ".page{page-break-after:always;margin:0;padding:0;overflow:hidden;}",
            ".page:last-child{page-break-after:auto;}",
            ".page img{display:block;}",
            "</style></head><body>",
        ]
        for image_path in image_pages:
            image_uri = image_path.resolve().as_uri()
            if image_path.suffix.lower() == ".svg":
                w, h = _svg_page_size_px(image_path)
            else:
                img = ImageReader(str(image_path))
                w, h = img.getSize()
            html_content.append(
                f"<div class='page' style='width:{w}px;height:{h}px'>"
                f"<img src='{html.escape(image_uri)}' style='width:{w}px;height:{h}px'>"
                "</div>"
            )
        html_content.append("</body></html>")
        html_path.write_text("".join(html_content), encoding="utf-8")

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
            await page.pdf(path=str(output_path), print_background=True, prefer_css_page_size=True)
            await browser.close()

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("PDF was not created or is empty.")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert .hwp/.hwpx -> .pdf via rhwp export-svg pipeline")
    parser.add_argument("input", type=Path, help="Input .hwp/.hwpx file path")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output .pdf file path")
    args = parser.parse_args()

    out = convert_hwp_to_pdf_with_rhwp(args.input, args.output)
    print(f"OK: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
