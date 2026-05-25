#!/usr/bin/env python3
"""Validate book chapter front matter and obvious reader-facing workflow leaks."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from common import ROOT, rel


REQUIRED_KEYS = {"id", "title", "order", "coverage"}
BANNED_WORKFLOW_TERMS = [
    "future unknown",
    "defer",
    "pool",
    "rebalance",
    "queued",
    "workflow",
]


def split_frontmatter(text: str) -> tuple[dict, str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    front = text[4:end]
    body = text[end + 5 :]
    data = yaml.safe_load(front) or {}
    return data, body


def main() -> int:
    chapters = sorted((ROOT / "book").glob("ch*.md"))
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()

    for path in chapters:
        text = path.read_text(encoding="utf-8")
        parsed = split_frontmatter(text)
        label = rel(path)
        if not parsed:
            errors.append(f"{label}: missing YAML front matter")
            continue
        data, body = parsed
        missing = sorted(REQUIRED_KEYS - set(data))
        if missing:
            errors.append(f"{label}: missing front matter keys {', '.join(missing)}")
        chapter_id = data.get("id")
        if chapter_id in seen_ids:
            errors.append(f"{label}: duplicate chapter id {chapter_id}")
        if chapter_id:
            seen_ids.add(str(chapter_id))
        lower_body = body.lower()
        for term in BANNED_WORKFLOW_TERMS:
            if term in lower_body:
                warnings.append(f"{label}: reader-facing body contains workflow term {term!r}")
        if re.search(r"新增.*20\d{2}|20\d{2}.*补充", body):
            warnings.append(f"{label}: body appears to contain dated update language")

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print(f"OK: checked {len(chapters)} chapter(s) ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

