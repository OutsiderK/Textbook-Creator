#!/usr/bin/env python3
"""Validate spec/open-questions.md structurally (soft severity).

Usage:
    python3 check_open_questions.py <project-root>

Each OQ block should have the form:

  ## OQ-NNN
  - 问题: ...
  - 入口章: chXX
  - 状态: open | closed
  - 期望章节: ...           (optional; only meaningful if status=open)
  - 关闭于: chXX            (required if status=closed)
  - 关闭 KP: <kp-id>         (required if status=closed)

Exits 0 even with warnings (soft severity). Returns 1 only if file structurally
unparseable (e.g., missing entirely).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

OQ_HEADER_RE = re.compile(r"^##\s+(OQ-\S+)\s*$", re.MULTILINE)


def strip_code_fences(text: str) -> str:
    """Replace fenced ``` blocks with blank lines so OQ headers inside docs are ignored."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    in_fence = False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append("\n")  # preserve line count for offsets
            continue
        out.append("\n" if in_fence else line)
    return "".join(out)


def parse_oq_blocks(text: str) -> list[tuple[str, str]]:
    """Return list of (oq_id, block_body) pairs (ignoring fenced code blocks)."""
    stripped = strip_code_fences(text)
    matches = list(OQ_HEADER_RE.finditer(stripped))
    blocks: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        oq_id = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(stripped)
        body = stripped[start:end]
        blocks.append((oq_id, body))
    return blocks


def extract_field(body: str, name: str) -> str | None:
    """Find a bullet line like '- 问题: ...' returning the value."""
    pattern = rf"^- {re.escape(name)}\s*[:：]\s*(.+?)\s*$"
    m = re.search(pattern, body, re.MULTILINE)
    return m.group(1).strip() if m else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root")
    args = parser.parse_args()

    oq_path = Path(args.project_root) / "spec" / "open-questions.md"
    if not oq_path.exists():
        print(f"⚠ {oq_path} not found (soft warning: may not be initialized yet)")
        sys.exit(0)

    text = oq_path.read_text(encoding="utf-8")
    blocks = parse_oq_blocks(text)

    warnings: list[str] = []
    seen_ids: set[str] = set()

    for oq_id, body in blocks:
        if oq_id in seen_ids:
            warnings.append(f"duplicate OQ id: {oq_id}")
        seen_ids.add(oq_id)

        problem = extract_field(body, "问题")
        entry = extract_field(body, "入口章")
        status = extract_field(body, "状态")

        if not problem:
            warnings.append(f"{oq_id}: missing 问题")
        if not entry:
            warnings.append(f"{oq_id}: missing 入口章")
        if status not in ("open", "closed"):
            warnings.append(f"{oq_id}: 状态 must be 'open' or 'closed', got '{status}'")

        if status == "closed":
            closed_in = extract_field(body, "关闭于")
            closed_by = extract_field(body, "关闭 KP")
            if not closed_in:
                warnings.append(f"{oq_id}: closed but missing 关闭于")
            if not closed_by:
                warnings.append(f"{oq_id}: closed but missing 关闭 KP")

    if not blocks:
        print(f"✓ open-questions.md present, no OQs registered")
        sys.exit(0)

    if warnings:
        for w in warnings:
            print(f"⚠ {w}")
        print(f"\n{len(warnings)} warning(s) in {len(blocks)} OQ(s) (soft severity)")
        sys.exit(0)

    print(f"✓ open-questions.md OK ({len(blocks)} OQs)")
    sys.exit(0)


if __name__ == "__main__":
    main()
