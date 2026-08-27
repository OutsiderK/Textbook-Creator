#!/usr/bin/env python3
"""Validate visual-review decisions and print final teaching-image pages."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


STATUS_ALIASES = {
    "confirmed": "confirmed",
    "confirm": "confirmed",
    "yes": "confirmed",
    "y": "confirmed",
    "teaching": "confirmed",
    "教学": "confirmed",
    "有图": "confirmed",
    "uncertain": "uncertain",
    "review": "uncertain",
    "maybe": "uncertain",
    "keep": "uncertain",
    "u": "uncertain",
    "不确定": "uncertain",
    "保留": "uncertain",
    "excluded": "excluded",
    "exclude": "excluded",
    "no": "excluded",
    "n": "excluded",
    "template": "excluded",
    "text": "excluded",
    "纯文字": "excluded",
    "模板": "excluded",
}


def fmt_pages(pages: list[int]) -> str:
    return ", ".join(map(str, pages)) if pages else "(none)"


def load_scan(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def normalize(value: str) -> str:
    key = value.strip().lower()
    return STATUS_ALIASES.get(key, key)


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize teaching-image pages from a visual-review decision CSV.")
    parser.add_argument("scan_json", type=Path)
    parser.add_argument("decisions_csv", type=Path)
    args = parser.parse_args()

    scan = load_scan(args.scan_json)
    required_pages = set(scan["summary"]["high_recall_pages"])
    decisions: dict[int, tuple[str, str]] = {}
    seen_pages: set[int] = set()
    errors: list[str] = []

    with args.decisions_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required_columns = {"page", "decision", "reason"}
        missing_columns = required_columns - set(reader.fieldnames or [])
        if missing_columns:
            errors.append(f"missing required CSV column(s): {', '.join(sorted(missing_columns))}")
        else:
            for row_num, row in enumerate(reader, start=2):
                raw_page = (row.get("page") or "").strip()
                try:
                    page = int(raw_page)
                except ValueError:
                    errors.append(f"row {row_num}: invalid page {raw_page!r}")
                    continue
                if page in decisions:
                    errors.append(f"row {row_num}: duplicate decision for page {page}")
                    continue
                seen_pages.add(page)
                decision = normalize(row.get("decision") or "")
                reason = (row.get("reason") or "").strip()
                if not decision:
                    errors.append(f"row {row_num}: blank decision for page {page}")
                    continue
                if decision not in {"confirmed", "uncertain", "excluded"}:
                    errors.append(f"row {row_num}: invalid decision {decision!r} for page {page}")
                    continue
                if page not in required_pages:
                    errors.append(f"row {row_num}: page {page} is not in high_recall_pages")
                    continue
                if decision == "excluded" and not reason:
                    errors.append(f"row {row_num}: excluded page {page} needs a reason")
                    continue
                decisions[page] = (decision, reason)

    missing_pages = sorted(required_pages - seen_pages)
    if missing_pages:
        errors.append(f"missing decisions for high_recall_pages: {fmt_pages(missing_pages)}")

    if errors:
        print("Decision validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    confirmed = sorted(page for page, (decision, _) in decisions.items() if decision == "confirmed")
    uncertain = sorted(page for page, (decision, _) in decisions.items() if decision == "uncertain")
    excluded = sorted(page for page, (decision, _) in decisions.items() if decision == "excluded")

    print(f"Confirmed teaching-image pages: {fmt_pages(confirmed)}")
    print(f"Uncertain / kept for no-miss recall: {fmt_pages(uncertain)}")
    print(f"Excluded as template-only after review: {fmt_pages(excluded)}")

    notable = [(page, reason) for page, (_, reason) in sorted(decisions.items()) if reason]
    if notable:
        print("Evidence:")
        for page, reason in notable:
            print(f"- {page}: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
