#!/usr/bin/env python3
"""Validate chapter file front-matter and surface forbidden scaffolding tokens.

Usage:
    python3 check_chapter_frontmatter.py <chapter-file.md> [chapter-file2.md ...]

Validates each chapter file:
  1. Has a YAML front-matter block at the top.
  2. Front-matter contains required keys: chapter, title, assumes, introduces,
     continues, open_questions, coverage.
  3. coverage references resolve to KPs in <project-root>/spec/knowledge-points.yaml
     (where <project-root> is detected from the chapter's containing book/ dir).
  4. Body contains no forbidden scaffolding tokens (defer, future-unknown, TODO,
     待补充, 新增, ⚡新增, v1, v2, etc.).

Exits 0 on pass, 1 on hard error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed.", file=sys.stderr)
    sys.exit(2)


REQUIRED_FM = {"chapter", "title", "assumes", "introduces", "continues", "open_questions", "coverage"}

# Forbidden tokens in body. Match as standalone tokens or substrings.
FORBIDDEN_TOKENS = [
    r"\bdefer\b",
    r"\bfuture[-_ ]unknown\b",
    r"\bTODO\b",
    r"待补充",
    r"⚡新增",
    r"\(将在第\s*[\d\w]+\s*章中讲解\)",   # parenthetical "(将在第 X 章中讲解)"
    r"\bv\d+\.\d+\b",                       # version markers v1.0
    r"\b本次更新\b",
    r"\b本次新增\b",
]

FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def find_project_root(chapter_path: Path) -> Path | None:
    """Walk up from chapter file to find the project root (containing spec/)."""
    p = chapter_path.resolve().parent
    while p != p.parent:
        if (p / "spec").is_dir():
            return p
        p = p.parent
    return None


def load_kp_ids(project_root: Path) -> set[str]:
    kp_path = project_root / "spec" / "knowledge-points.yaml"
    if not kp_path.exists():
        return set()
    try:
        data = yaml.safe_load(kp_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return set()
    if isinstance(data, dict):
        kps = data.get("knowledge_points", []) or []
    elif isinstance(data, list):
        kps = data
    else:
        kps = []
    return {kp["id"] for kp in kps if isinstance(kp, dict) and "id" in kp}


def check_chapter(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"{path}: file does not exist"]

    text = path.read_text(encoding="utf-8")

    # 1. Front-matter present
    m = FRONT_MATTER_RE.match(text)
    if not m:
        errors.append(f"{path}: missing YAML front-matter at top (--- ... ---)")
        # we can still scan body even without front-matter
        fm = {}
        body = text
    else:
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as e:
            errors.append(f"{path}: front-matter YAML parse error: {e}")
            fm = {}
        body = text[m.end():]

    # 2. Required fields
    if isinstance(fm, dict):
        missing = REQUIRED_FM - set(fm.keys())
        if missing:
            errors.append(f"{path}: front-matter missing fields: {sorted(missing)}")

        # coverage must be a list of strings
        coverage = fm.get("coverage")
        if coverage is not None and not isinstance(coverage, list):
            errors.append(f"{path}: front-matter coverage must be a list")

        # 3. Cross-ref coverage IDs against ledger
        project_root = find_project_root(path)
        if project_root and isinstance(coverage, list):
            known_ids = load_kp_ids(project_root)
            if known_ids:
                for kp_id in coverage:
                    if kp_id not in known_ids:
                        errors.append(f"{path}: coverage references unknown KP id '{kp_id}'")

    # 4. Forbidden tokens in body
    for pattern in FORBIDDEN_TOKENS:
        for m in re.finditer(pattern, body):
            line_num = body[:m.start()].count("\n") + 1
            snippet = body.splitlines()[line_num - 1] if line_num - 1 < len(body.splitlines()) else ""
            errors.append(
                f"{path}:body+{line_num}: forbidden token '{m.group(0)}' "
                f"in line: {snippet.strip()[:80]}"
            )

    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("chapters", nargs="+", help="Chapter markdown file(s)")
    args = parser.parse_args()

    all_errors: list[str] = []
    for chapter in args.chapters:
        errs = check_chapter(Path(chapter))
        all_errors.extend(errs)

    if all_errors:
        for e in all_errors:
            print(f"✗ {e}")
        print(f"\n{len(all_errors)} error(s)")
        sys.exit(1)

    print(f"✓ {len(args.chapters)} chapter file(s) OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
