#!/usr/bin/env python3
"""High-recall scan for course-PDF pages that contain instructional images."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF


@dataclass
class ImageHit:
    index: int
    bbox: list[float]
    area_frac: float
    width_frac: float
    height_frac: float
    center: list[float]
    intrinsic_width: int | None
    intrinsic_height: int | None
    xref: int | None
    digest: str
    position: str
    repeat_hash_pages: int
    repeat_bbox_pages: int
    is_template: bool = False
    template_reasons: list[str] = field(default_factory=list)
    teaching_reasons: list[str] = field(default_factory=list)


@dataclass
class PageReport:
    page: int
    status: str
    score: float
    reasons: list[str]
    image_count: int
    non_template_count: int
    template_count: int
    images: list[ImageHit]


def sha16(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()[:16]


def digest_from_info(info: dict[str, Any]) -> str:
    digest = info.get("digest")
    if isinstance(digest, bytes):
        return digest.hex()[:16]
    if isinstance(digest, str) and digest:
        return digest[:16]
    payload = repr(
        (
            info.get("xref"),
            info.get("width"),
            info.get("height"),
            tuple(round(x, 2) for x in info.get("bbox", ())),
        )
    ).encode("utf-8")
    return sha16(payload)


def position_label(cx: float, cy: float, area_frac: float, width_frac: float, height_frac: float) -> str:
    if area_frac >= 0.65:
        return "background"
    if cy < 0.13 and height_frac < 0.18:
        return "header"
    if cy > 0.87 and height_frac < 0.18:
        return "footer"
    if cx < 0.14 and width_frac < 0.22:
        return "left-margin"
    if cx > 0.86 and width_frac < 0.22:
        return "right-margin"
    if 0.22 <= cx <= 0.78 and 0.18 <= cy <= 0.82:
        return "body"
    return "edge"


def quant_bbox(bbox: list[float], page_width: float, page_height: float) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    return (
        round(x0 / page_width * 100),
        round(y0 / page_height * 100),
        round(x1 / page_width * 100),
        round(y1 / page_height * 100),
    )


def page_image_infos(page: fitz.Page) -> list[dict[str, Any]]:
    try:
        infos = page.get_image_info(hashes=True, xrefs=True)
    except TypeError:
        infos = page.get_image_info()
    except Exception:
        infos = []

    if infos:
        return [dict(info) for info in infos if info.get("bbox")]

    # Fallback for older PyMuPDF versions.
    blocks = page.get_text("dict").get("blocks", [])
    found: list[dict[str, Any]] = []
    for block in blocks:
        if block.get("type") != 1 or "bbox" not in block:
            continue
        image_bytes = block.get("image") or b""
        found.append(
            {
                "bbox": block["bbox"],
                "width": block.get("width"),
                "height": block.get("height"),
                "xref": block.get("xref", 0),
                "digest": sha16(image_bytes) if image_bytes else "",
            }
        )
    return found


def collect_images(doc: fitz.Document) -> tuple[list[list[ImageHit]], Counter, Counter, dict[str, set[int]], dict[tuple[str, tuple[int, int, int, int]], set[int]]]:
    pages: list[list[ImageHit]] = []
    hash_pages: dict[str, set[int]] = defaultdict(set)
    bbox_pages: dict[tuple[str, tuple[int, int, int, int]], set[int]] = defaultdict(set)
    hash_counter: Counter = Counter()
    bbox_counter: Counter = Counter()

    provisional: list[list[tuple[ImageHit, tuple[str, tuple[int, int, int, int]]]]] = []
    for page_idx, page in enumerate(doc):
        rect = page.rect
        page_area = max(rect.width * rect.height, 1.0)
        items: list[tuple[ImageHit, tuple[str, tuple[int, int, int, int]]]] = []
        for img_idx, info in enumerate(page_image_infos(page)):
            bbox_rect = fitz.Rect(info["bbox"])
            if bbox_rect.is_empty or bbox_rect.width <= 1 or bbox_rect.height <= 1:
                continue
            bbox = [float(bbox_rect.x0), float(bbox_rect.y0), float(bbox_rect.x1), float(bbox_rect.y1)]
            area_frac = min((bbox_rect.width * bbox_rect.height) / page_area, 1.0)
            width_frac = min(bbox_rect.width / max(rect.width, 1.0), 1.0)
            height_frac = min(bbox_rect.height / max(rect.height, 1.0), 1.0)
            cx = (bbox_rect.x0 + bbox_rect.x1) / 2 / max(rect.width, 1.0)
            cy = (bbox_rect.y0 + bbox_rect.y1) / 2 / max(rect.height, 1.0)
            digest = digest_from_info(info)
            qb = quant_bbox(bbox, rect.width, rect.height)
            key = (digest, qb)
            hit = ImageHit(
                index=img_idx,
                bbox=[round(x, 2) for x in bbox],
                area_frac=round(area_frac, 5),
                width_frac=round(width_frac, 5),
                height_frac=round(height_frac, 5),
                center=[round(cx, 4), round(cy, 4)],
                intrinsic_width=info.get("width"),
                intrinsic_height=info.get("height"),
                xref=info.get("xref") or None,
                digest=digest,
                position=position_label(cx, cy, area_frac, width_frac, height_frac),
                repeat_hash_pages=0,
                repeat_bbox_pages=0,
            )
            items.append((hit, key))
            hash_pages[digest].add(page_idx + 1)
            bbox_pages[key].add(page_idx + 1)
            hash_counter[digest] += 1
            bbox_counter[key] += 1
        provisional.append(items)

    for page_items in provisional:
        finalized: list[ImageHit] = []
        for hit, key in page_items:
            hit.repeat_hash_pages = len(hash_pages[hit.digest])
            hit.repeat_bbox_pages = len(bbox_pages[key])
            finalized.append(hit)
        pages.append(finalized)
    return pages, hash_counter, bbox_counter, hash_pages, bbox_pages


def classify_templates(pages: list[list[ImageHit]], page_count: int) -> None:
    repeat_threshold = max(4, math.ceil(page_count * 0.15))
    very_common_threshold = max(5, math.ceil(page_count * 0.45))

    for page_images in pages:
        for hit in page_images:
            repeated_same_place = hit.repeat_bbox_pages >= repeat_threshold
            repeated_same_asset = hit.repeat_hash_pages >= very_common_threshold
            small_or_margin = hit.area_frac <= 0.025 or hit.position in {"header", "footer", "left-margin", "right-margin"}
            background = hit.area_frac >= 0.65
            decorative_strip = hit.height_frac < 0.14 and hit.width_frac > 0.35 and hit.position in {"header", "footer"}

            if repeated_same_place and small_or_margin:
                hit.is_template = True
                hit.template_reasons.append(f"repeats at same position on {hit.repeat_bbox_pages} pages")
            if repeated_same_asset and small_or_margin:
                hit.is_template = True
                hit.template_reasons.append(f"common marginal asset on {hit.repeat_hash_pages} pages")
            if repeated_same_place and background:
                hit.is_template = True
                hit.template_reasons.append(f"repeated background on {hit.repeat_bbox_pages} pages")
            if repeated_same_place and decorative_strip:
                hit.is_template = True
                hit.template_reasons.append("repeated header/footer strip")


def score_page(images: list[ImageHit]) -> tuple[str, float, list[str]]:
    if not images:
        return "no_images", 0.0, ["no embedded raster images detected"]

    non_template = [img for img in images if not img.is_template]
    templates = [img for img in images if img.is_template]
    score = 0.0
    reasons: list[str] = []

    for img in non_template:
        strong = False
        if img.area_frac >= 0.015:
            strong = True
            img.teaching_reasons.append(f"non-template image covers {img.area_frac:.1%} of slide")
        if img.position == "body" and img.area_frac >= 0.006:
            strong = True
            img.teaching_reasons.append("non-template image is in the body area")
        if (img.intrinsic_width or 0) >= 120 and (img.intrinsic_height or 0) >= 120 and img.area_frac >= 0.004:
            strong = True
            img.teaching_reasons.append("image has instructional-scale pixel dimensions")
        if strong:
            score += 1.0 + min(img.area_frac * 18, 4.0)
        elif img.area_frac >= 0.003:
            score += 0.35
            img.teaching_reasons.append("small unique image; keep for recall review")

    non_template_area = sum(img.area_frac for img in non_template)
    central_large_template = [
        img
        for img in templates
        if img.position == "body" and img.area_frac >= 0.08 and img.repeat_hash_pages < max(8, len(images) + 1)
    ]

    if non_template:
        reasons.append(f"{len(non_template)} non-template image(s)")
    if templates:
        reasons.append(f"{len(templates)} likely template/decorative image(s)")
    if non_template_area >= 0.025:
        score += 1.0
        reasons.append(f"non-template image area totals {non_template_area:.1%}")
    if len([img for img in non_template if img.area_frac >= 0.004]) >= 2:
        score += 0.8
        reasons.append("multiple non-template images")

    if score >= 1.2:
        return "likely_teaching_image", round(score, 3), reasons
    if non_template:
        return "review", round(score, 3), reasons + ["weak unique image signal; visually review"]
    if central_large_template:
        return "review", 0.5, reasons + ["large body image was template-like; review before excluding"]
    return "template_only", 0.0, reasons or ["only repeated template/decorative images detected"]


def render_contact_sheets(doc: fitz.Document, pages: list[int], out_dir: Path, name: str, dpi: int, cols: int, max_per_sheet: int) -> list[str]:
    if not pages:
        return []
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return []

    out_paths: list[str] = []
    scale = dpi / 72
    for sheet_idx, start in enumerate(range(0, len(pages), max_per_sheet), start=1):
        subset = pages[start : start + max_per_sheet]
        thumbs: list[Image.Image] = []
        for page_num in subset:
            pix = doc[page_num - 1].get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            label_h = 26
            labeled = Image.new("RGB", (img.width, img.height + label_h), "white")
            labeled.paste(img, (0, label_h))
            draw = ImageDraw.Draw(labeled)
            draw.rectangle([0, 0, img.width, label_h], fill=(255, 255, 255))
            draw.text((6, 6), f"p.{page_num}", fill=(0, 0, 0))
            thumbs.append(labeled)

        max_w = max(t.width for t in thumbs)
        max_h = max(t.height for t in thumbs)
        rows = math.ceil(len(thumbs) / cols)
        sheet = Image.new("RGB", (cols * max_w, rows * max_h), "white")
        for idx, thumb in enumerate(thumbs):
            x = (idx % cols) * max_w
            y = (idx // cols) * max_h
            sheet.paste(thumb, (x, y))
        path = out_dir / f"{name}_{sheet_idx:02d}.jpg"
        sheet.save(path, quality=88)
        out_paths.append(str(path))
    return out_paths


def write_markdown(report: dict[str, Any], path: Path) -> None:
    def pages_line(name: str, pages: list[int]) -> str:
        return f"- **{name}:** " + (", ".join(map(str, pages)) if pages else "(none)")

    lines = [
        "# Teaching Image Page Scan",
        "",
        "This is a high-recall scan. For a no-miss workflow, start from `high_recall_pages` and remove pages only after visual review confirms they contain template/decorative imagery only.",
        "",
        pages_line("High recall pages", report["summary"]["high_recall_pages"]),
        pages_line("Likely teaching-image pages", report["summary"]["likely_pages"]),
        pages_line("Needs visual review", report["summary"]["review_pages"]),
        pages_line("Template-only pages", report["summary"]["template_only_pages"]),
        "",
        "## Page Details",
        "",
    ]
    for page in report["pages"]:
        if page["status"] == "no_images":
            continue
        lines.append(f"### Page {page['page']}: {page['status']} (score {page['score']})")
        lines.append("- " + "; ".join(page["reasons"]))
        for img in page["images"]:
            tag = "template" if img["is_template"] else "candidate"
            details = img["template_reasons"] if img["is_template"] else img["teaching_reasons"]
            reason = "; ".join(details) if details else "no extra reason"
            lines.append(
                f"  - image {img['index']} [{tag}], area {img['area_frac']:.1%}, pos {img['position']}, repeats {img['repeat_hash_pages']} pages: {reason}"
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_review_template(report: dict[str, Any], path: Path) -> None:
    high_recall = set(report["summary"]["high_recall_pages"])
    by_page = {page["page"]: page for page in report["pages"]}
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["page", "decision", "reason", "scan_status", "score", "scan_reasons"],
        )
        writer.writeheader()
        for page_num in sorted(high_recall):
            page = by_page[page_num]
            writer.writerow(
                {
                    "page": page_num,
                    "decision": "",
                    "reason": "",
                    "scan_status": page["status"],
                    "score": page["score"],
                    "scan_reasons": "; ".join(page["reasons"]),
                }
            )


def scan(pdf: Path, out_dir: Path, dpi: int, cols: int, max_per_sheet: int) -> dict[str, Any]:
    doc = fitz.open(pdf)
    pages_images, _, _, _, _ = collect_images(doc)
    classify_templates(pages_images, len(doc))

    page_reports: list[PageReport] = []
    for idx, images in enumerate(pages_images, start=1):
        status, score, reasons = score_page(images)
        page_reports.append(
            PageReport(
                page=idx,
                status=status,
                score=score,
                reasons=reasons,
                image_count=len(images),
                non_template_count=len([img for img in images if not img.is_template]),
                template_count=len([img for img in images if img.is_template]),
                images=images,
            )
        )

    likely = [p.page for p in page_reports if p.status == "likely_teaching_image"]
    review = [p.page for p in page_reports if p.status == "review"]
    template_only = [p.page for p in page_reports if p.status == "template_only"]
    high_recall = sorted(set(likely + review))

    out_dir.mkdir(parents=True, exist_ok=True)
    sheets = {
        "high_recall": render_contact_sheets(doc, high_recall, out_dir, "contact_high_recall", dpi, cols, max_per_sheet),
        "review": render_contact_sheets(doc, review, out_dir, "contact_review", dpi, cols, max_per_sheet),
        "template_only": render_contact_sheets(doc, template_only[:max_per_sheet], out_dir, "contact_template_audit", dpi, cols, max_per_sheet),
    }

    report = {
        "input_pdf": str(pdf),
        "page_count": len(doc),
        "summary": {
            "high_recall_pages": high_recall,
            "likely_pages": likely,
            "review_pages": review,
            "template_only_pages": template_only,
            "no_image_pages": [p.page for p in page_reports if p.status == "no_images"],
            "contact_sheets": sheets,
        },
        "pages": [asdict(page) for page in page_reports],
    }
    (out_dir / "teaching_image_pages.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(report, out_dir / "teaching_image_pages.md")
    write_review_template(report, out_dir / "review_decisions_template.csv")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Find high-recall candidate pages with teaching images in a course PPT PDF.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, default=Path("teaching-image-scan"))
    parser.add_argument("--thumb-dpi", type=int, default=55, help="DPI for contact-sheet thumbnails.")
    parser.add_argument("--cols", type=int, default=5)
    parser.add_argument("--max-per-sheet", type=int, default=35)
    args = parser.parse_args()

    report = scan(args.pdf, args.out, args.thumb_dpi, args.cols, args.max_per_sheet)
    summary = report["summary"]
    print("high_recall_pages:", ",".join(map(str, summary["high_recall_pages"])) or "(none)")
    print("likely_pages:", ",".join(map(str, summary["likely_pages"])) or "(none)")
    print("review_pages:", ",".join(map(str, summary["review_pages"])) or "(none)")
    print("json:", args.out / "teaching_image_pages.json")
    print("markdown:", args.out / "teaching_image_pages.md")
    print("review_template:", args.out / "review_decisions_template.csv")
    for label, paths in summary["contact_sheets"].items():
        if paths:
            print(f"{label}_contact_sheets:", ", ".join(paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
