from pathlib import Path


def unique_path(path: Path) -> Path:
    """이미 존재하는 파일명이면 (1), (2)... 형태로 중복을 피한다."""
    if not path.exists():
        return path
    stem   = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
