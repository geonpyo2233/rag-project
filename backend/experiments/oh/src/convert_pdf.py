from pathlib import Path
import subprocess


SOFFICE_PATH = r"C:\Program Files\LibreOffice\program\soffice.exe"


def convert_docx_to_pdf(input_file: Path, output_dir: Path):
    print("\n===== STEP 02 : DOCX TO PDF =====")

    output_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            SOFFICE_PATH,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(input_file),
        ],
        check=True
    )

    pdf_path = output_dir / f"{input_file.stem}.pdf"

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF 변환 실패:\n{pdf_path}"
        )

    print("\nPDF 변환 완료")
    print(pdf_path)

    return pdf_path