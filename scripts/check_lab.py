#!/usr/bin/env python3
"""Validate a lab directory.

Usage:
    python3 check_lab.py <lab-dir>

Reads <lab-dir>/README.md to detect lab type, then validates:
  - README has required sections (学习目标, 你将做什么, 验证)
  - For code labs (python-simulator, c-posix, mini-kernel): verify.sh exists
    and runs successfully against the solution.
  - For observation labs: expected-observations.md exists.
  - No date/version markers in any *.md file under the lab.

Exits 0 on pass; 1 on hard fail.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


REQUIRED_README_HEADINGS = ["## 学习目标", "## 你将做什么", "## 验证"]
DATE_VERSION_PATTERNS = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\bv\d+\.\d+\b"),
    re.compile(r"本次更新"),
    re.compile(r"本次新增"),
]
LAB_TYPE_RE = re.compile(r"<!--\s*lab[-_ ]type:\s*([a-z_-]+)\s*-->", re.IGNORECASE)


def detect_lab_type(readme_text: str) -> str:
    """Detect lab type from an HTML comment marker, or fall back to heuristics."""
    m = LAB_TYPE_RE.search(readme_text)
    if m:
        return m.group(1).lower()
    # Heuristic fallback
    lower = readme_text.lower()
    if "observation" in lower or "观察" in readme_text:
        return "observation"
    if "python" in lower:
        return "python-simulator"
    if "xv6" in lower or "nemu" in lower or "nachos" in lower:
        return "mini-kernel"
    if "verify.sh" in lower:
        return "code"
    return "unknown"


def check_lab(lab_dir: Path) -> list[str]:
    errors: list[str] = []

    if not lab_dir.is_dir():
        return [f"{lab_dir}: not a directory"]

    readme = lab_dir / "README.md"
    if not readme.exists():
        return [f"{lab_dir}: missing README.md"]

    text = readme.read_text(encoding="utf-8")

    # Required headings
    for heading in REQUIRED_README_HEADINGS:
        if heading not in text:
            errors.append(f"{readme}: missing required heading '{heading}'")

    lab_type = detect_lab_type(text)

    # Type-specific checks
    if lab_type == "observation":
        if not (lab_dir / "expected-observations.md").exists():
            errors.append(f"{lab_dir}: observation lab missing expected-observations.md")
    elif lab_type in ("python-simulator", "c-posix", "mini-kernel", "code"):
        verify = lab_dir / "verify.sh"
        if not verify.exists():
            errors.append(f"{lab_dir}: code lab missing verify.sh")
        else:
            # Try to run verify against solution if it exists
            solution = lab_dir / "solution"
            if solution.is_dir() and verify.exists():
                try:
                    result = subprocess.run(
                        ["bash", verify.name],
                        cwd=lab_dir,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    if result.returncode != 0:
                        errors.append(
                            f"{lab_dir}: verify.sh exit={result.returncode} against solution\n"
                            f"  stderr: {result.stderr[:200]}"
                        )
                except subprocess.TimeoutExpired:
                    errors.append(f"{lab_dir}: verify.sh timed out (>60s)")
                except FileNotFoundError:
                    errors.append(f"{lab_dir}: bash not available to run verify.sh")

    # Scan all md files for date/version markers
    for md in lab_dir.rglob("*.md"):
        md_text = md.read_text(encoding="utf-8")
        for pat in DATE_VERSION_PATTERNS:
            for m in pat.finditer(md_text):
                line_num = md_text[:m.start()].count("\n") + 1
                errors.append(
                    f"{md}:body+{line_num}: forbidden date/version marker '{m.group(0)}'"
                )

    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("lab_dir")
    args = parser.parse_args()

    errors = check_lab(Path(args.lab_dir))
    if errors:
        for e in errors:
            print(f"✗ {e}")
        print(f"\n{len(errors)} error(s)")
        sys.exit(1)

    print(f"✓ {args.lab_dir} OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
