#!/usr/bin/env python3
"""Build a reproducible, self-contained online-course-textbook release ZIP."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".py", ".yaml", ".yml", ".json", ".txt", ".csv"}
EXCLUDED_PARTS = {".git", "__pycache__"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
FORBIDDEN_REFERENCES = {
    "retired external skill": "find-teaching-" + "image-slides",
    "machine-specific skill path": "/home/coder/.codex/" + "skills",
}


def release_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if not path.is_file():
            continue
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.suffix in EXCLUDED_SUFFIXES:
            continue
        files.append(path)
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def validate_self_contained(files: list[Path]) -> None:
    errors: list[str] = []
    for path in files:
        if path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, marker in FORBIDDEN_REFERENCES.items():
            if marker in text:
                errors.append(f"{path.relative_to(ROOT)} contains {label}: {marker}")
    if errors:
        raise SystemExit("release self-containment check failed:\n- " + "\n- ".join(errors))


def zip_info(path: Path) -> ZipInfo:
    relative = Path(ROOT.name) / path.relative_to(ROOT)
    info = ZipInfo(relative.as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
    return info


def build(output: Path) -> tuple[int, str]:
    output = output.resolve()
    try:
        output.relative_to(ROOT)
    except ValueError:
        pass
    else:
        raise SystemExit("release output must be outside the skill directory")

    files = release_files()
    validate_self_contained(files)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.writestr(zip_info(path), path.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
    with ZipFile(temporary) as archive:
        bad_member = archive.testzip()
        if bad_member:
            temporary.unlink(missing_ok=True)
            raise SystemExit(f"release integrity check failed at {bad_member}")
    os.replace(temporary, output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return len(files), digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Destination .zip path outside the skill directory")
    args = parser.parse_args()
    count, digest = build(args.output)
    print(f"release: {args.output.resolve()}")
    print(f"files: {count}")
    print(f"sha256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
