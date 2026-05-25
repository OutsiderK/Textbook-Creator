#!/usr/bin/env python3
"""Validate spec/open-questions.md structure."""

from __future__ import annotations

import re

from common import ROOT


ENTRY_RE = re.compile(r"^- \[(?P<mark>[ xX])\]\s+(?P<id>OQ-\d{4})\b(?P<title>.*)$")


def main() -> int:
    path = ROOT / "spec" / "open-questions.md"
    if not path.exists():
        print("ERROR: missing spec/open-questions.md")
        return 1
    lines = path.read_text(encoding="utf-8").splitlines()
    ids: dict[str, int] = {}
    errors: list[str] = []
    warnings: list[str] = []

    in_comment = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("<!--"):
            in_comment = True
        if in_comment:
            if stripped.endswith("-->"):
                in_comment = False
            continue
        match = ENTRY_RE.match(line)
        if not match:
            continue
        oq_id = match.group("id")
        if oq_id in ids:
            errors.append(f"{oq_id}: duplicate entry at lines {ids[oq_id]} and {idx + 1}")
        ids[oq_id] = idx + 1
        window = "\n".join(lines[idx + 1 : idx + 6])
        if "raised_in:" not in window:
            warnings.append(f"{oq_id}: missing raised_in detail")
        if match.group("mark").lower() == "x" and "answered_by:" not in window:
            errors.append(f"{oq_id}: closed question must include answered_by")

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print(f"OK: checked {len(ids)} open question(s) ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
