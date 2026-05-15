from hwp_extract import HWPExtractor
from pathlib import Path

#HWP 추출 테스트 코드
path = Path(__file__).parent / "testa.hwp"
with path.open("rb") as f:
    data = f.read()

output_folder = Path("./hwpa")

if not os.path.exists(output_folder):
    os.makedirs(output_folder)

bn = "testa.hwp"

document = HWPExtractor(data=data)
for idx, obj in enumerate(document.extract_files()):
    object_name = "".join([c for c in obj.name if c.isalnum() or c in ["_", "."]])
    target_path = output_folder / f"{bn}_{idx}_{object_name}"
    print(f"Writing extracted file to: {target_path}")
    with target_path.open("wb") as outf:
        outf.write(obj.data)