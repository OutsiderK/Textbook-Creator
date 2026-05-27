#!/usr/bin/env python3
"""Validate Stage A page-risk audit evidence."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


VALID_RISK = {"high", "medium", "low", "section_divider"}
VALID_PAGE_CLASS = {
    "process_diagram",
    "architecture_diagram",
    "state_machine",
    "comparison_table",
    "formula_derivation",
    "chart_or_plot",
    "code_or_command",
    "case_steps",
    "taxonomy",
    "table",
    "screenshot_or_scanned",
    "section_divider",
    "text_dense",
    "normal_text",
}


def load_yaml(path: Path) -> Any:
    if not path.exists():
        raise SystemExit(f"ERROR: {path} does not exist")
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise SystemExit(f"ERROR: {path} is empty")
    data = yaml.safe_load(text)
    if data is None:
        raise SystemExit(f"ERROR: {path} has no YAML content")
    return data


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def as_page_map(items: Any, label: str, errors: list[str]) -> dict[int, dict[str, Any]]:
    if not isinstance(items, list):
        errors.append(f"{label} must be a list")
        return {}
    out: dict[int, dict[str, Any]] = {}
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{label}[{i}] must be a mapping")
            continue
        page = item.get("page")
        if not isinstance(page, int) or page < 1:
            errors.append(f"{label}[{i}].page must be a positive integer")
            continue
        if page in out:
            errors.append(f"{label}: duplicate page {page}")
        out[page] = item
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audit", help="docs/page-risk-<batch>.yaml")
    args = parser.parse_args()

    path = Path(args.audit)
    data = load_yaml(path)
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict):
        errors.append("audit root must be a mapping")
        data = {}

    summary = data.get("summary") or {}
    pages_total = summary.get("pages_total")
    if not isinstance(pages_total, int) or pages_total < 1:
        errors.append("summary.pages_total must be a positive integer")

    thumbnail_scan = as_page_map(data.get("thumbnail_scan"), "thumbnail_scan", errors)
    classification_review = as_page_map(
        data.get("classification_review") or [], "classification_review", errors
    )
    page_risks = as_page_map(data.get("page_risks"), "page_risks", errors)

    if isinstance(pages_total, int) and pages_total >= 1:
        expected = set(range(1, pages_total + 1))
        for label, page_map in (
            ("thumbnail_scan", thumbnail_scan),
            ("page_risks", page_risks),
        ):
            missing = sorted(expected - set(page_map))
            extra = sorted(set(page_map) - expected)
            if missing:
                errors.append(f"{label} missing page(s): {missing[:20]}")
            if extra:
                errors.append(f"{label} has page(s) outside summary.pages_total: {extra[:20]}")

    for page, item in thumbnail_scan.items():
        prefix = f"thumbnail_scan page {page}"
        if not non_empty_string(item.get("thumbnail_observation")):
            errors.append(f"{prefix}: thumbnail_observation is required")
        candidate = item.get("visual_candidate")
        if not isinstance(candidate, bool):
            errors.append(f"{prefix}: visual_candidate must be bool")
        reasons = item.get("candidate_reason")
        if reasons is None:
            errors.append(f"{prefix}: candidate_reason is required (use [] if false)")
        elif not isinstance(reasons, list):
            errors.append(f"{prefix}: candidate_reason must be a list")
        elif candidate and not reasons:
            errors.append(f"{prefix}: visual_candidate=true requires candidate_reason")

    for page, risk in page_risks.items():
        prefix = f"page_risks page {page}"
        risk_level = risk.get("risk_level")
        page_class = risk.get("page_class")
        if risk_level not in VALID_RISK:
            errors.append(f"{prefix}: invalid risk_level {risk_level!r}")
        if page_class not in VALID_PAGE_CLASS:
            errors.append(f"{prefix}: invalid page_class {page_class!r}")

        thumb = risk.get("thumbnail")
        if not isinstance(thumb, dict):
            errors.append(f"{prefix}: thumbnail mapping is required")
            continue
        candidate = thumb.get("visual_candidate")
        if not isinstance(candidate, bool):
            errors.append(f"{prefix}: thumbnail.visual_candidate must be bool")
        if not non_empty_string(thumb.get("observation")):
            errors.append(f"{prefix}: thumbnail.observation is required")

        scan = thumbnail_scan.get(page)
        if scan and isinstance(candidate, bool) and candidate != scan.get("visual_candidate"):
            errors.append(f"{prefix}: thumbnail.visual_candidate disagrees with thumbnail_scan")

        review = risk.get("classification_review")
        if candidate is True:
            if page not in classification_review:
                errors.append(f"{prefix}: visual_candidate=true requires classification_review entry")
            if not isinstance(review, dict):
                errors.append(f"{prefix}: classification_review mapping is required")
                continue
            if review.get("required") is not True:
                errors.append(f"{prefix}: classification_review.required must be true")
            if review.get("completed") is not True:
                errors.append(f"{prefix}: classification_review.completed must be true")
            decision = review.get("decision")
            if decision not in VALID_RISK:
                errors.append(f"{prefix}: classification_review.decision invalid {decision!r}")
            elif risk_level != decision:
                errors.append(f"{prefix}: risk_level must match classification_review.decision")

            full_review = classification_review.get(page) or {}
            if full_review.get("opened_rendered_page") is not True:
                errors.append(f"classification_review page {page}: opened_rendered_page must be true")
            if not non_empty_string(full_review.get("visual_observation")):
                errors.append(f"classification_review page {page}: visual_observation is required")
            if full_review.get("decision") != decision:
                errors.append(f"classification_review page {page}: decision disagrees with page_risks")

            if decision == "section_divider":
                evidence = full_review.get("demotion_evidence")
                if not isinstance(evidence, dict):
                    errors.append(
                        f"classification_review page {page}: section_divider demotion_evidence is required"
                    )
                else:
                    if evidence.get("substantive_visual") is not False:
                        errors.append(
                            f"classification_review page {page}: demotion_evidence.substantive_visual must be false"
                        )
                    if not any(
                        evidence.get(key) is True
                        for key in ("template_or_decorative_only", "non_instructional_visual")
                    ):
                        errors.append(
                            f"classification_review page {page}: demotion_evidence must explain why visual is safe"
                        )
        else:
            if isinstance(review, dict) and review.get("required") is True:
                warnings.append(f"{prefix}: classification_review.required=true but visual_candidate is false")

    for page, review in classification_review.items():
        prefix = f"classification_review page {page}"
        if review.get("opened_rendered_page") is not True:
            errors.append(f"{prefix}: opened_rendered_page must be true")
        if not non_empty_string(review.get("visual_observation")):
            errors.append(f"{prefix}: visual_observation is required")
        if review.get("decision") not in VALID_RISK:
            errors.append(f"{prefix}: invalid decision {review.get('decision')!r}")
        page_class = review.get("page_class")
        if page_class is not None and page_class not in VALID_PAGE_CLASS:
            errors.append(f"{prefix}: invalid page_class {page_class!r}")

    high_pages = {
        item.get("page")
        for item in data.get("review_queue") or []
        if isinstance(item, dict) and item.get("risk_level") == "high"
    }
    risk_high_pages = {
        page for page, item in page_risks.items() if item.get("risk_level") == "high"
    }
    missing_high = sorted(risk_high_pages - high_pages)
    if missing_high:
        errors.append(f"review_queue missing high page(s): {missing_high[:20]}")

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print(
        f"OK: checked page-risk audit {path} "
        f"({len(page_risks)} page risk(s), {len(classification_review)} classification review(s), "
        f"{len(warnings)} warning(s))"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
