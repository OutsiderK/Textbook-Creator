#!/usr/bin/env python3
"""Render selected PDF pages for Stage A visual_page_notes."""

from __future__ import annotations

import argparse
from pathlib import Path

import fitz


def parse_pages(spec: str) -> list[int]:
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start < 1 or end < start:
                raise argparse.ArgumentTypeError(f"invalid page range: {part}")
            pages.update(range(start, end + 1))
        else:
            page = int(part)
            if page < 1:
                raise argparse.ArgumentTypeError(f"invalid page number: {part}")
            pages.add(page)
    if not pages:
        raise argparse.ArgumentTypeError("at least one page is required")
    return sorted(pages)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", help="PDF/PPT-exported PDF path")
    parser.add_argument("--pages", required=True, type=parse_pages, help="1-indexed pages, e.g. 3,7,10-12")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--scale", type=float, default=2.0, help="render scale, default: 2")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        raise SystemExit(f"ERROR: {pdf_path} does not exist")
    if args.scale <= 0:
        raise SystemExit("ERROR: --scale must be positive")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf_path))
    matrix = fitz.Matrix(args.scale, args.scale)
    for page_no in args.pages:
        if page_no > doc.page_count:
            raise SystemExit(
                f"ERROR: page {page_no} outside document range 1..{doc.page_count}"
            )
        page = doc[page_no - 1]
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        out_path = out_dir / f"p{page_no:03d}.png"
        pix.save(out_path)
        print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
