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
VALID_NOTE_SOURCE = {"teaching_image", "comprehension_blocker"}
VALID_CONFIDENCE = {"high", "medium", "uncertain"}


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


def non_empty_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def int_list(value: Any, label: str, errors: list[str]) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return []
    out: list[int] = []
    for i, item in enumerate(value):
        if not isinstance(item, int) or item < 1:
            errors.append(f"{label}[{i}] must be a positive integer")
            continue
        out.append(item)
    return out


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


def validate_pages_total(data: dict[str, Any], errors: list[str]) -> int | None:
    summary = data.get("summary") or {}
    pages_total = summary.get("pages_total")
    if not isinstance(pages_total, int) or pages_total < 1:
        errors.append("summary.pages_total must be a positive integer")
        return None
    return pages_total


def validate_page_coverage(
    pages_total: int | None,
    page_map: dict[int, dict[str, Any]],
    label: str,
    errors: list[str],
) -> None:
    if pages_total is None:
        return
    expected = set(range(1, pages_total + 1))
    missing = sorted(expected - set(page_map))
    extra = sorted(set(page_map) - expected)
    if missing:
        errors.append(f"{label} missing page(s): {missing[:20]}")
    if extra:
        errors.append(f"{label} has page(s) outside summary.pages_total: {extra[:20]}")


def validate_v1(data: dict[str, Any]) -> tuple[list[str], list[str], dict[str, int]]:
    errors: list[str] = []
    warnings: list[str] = []
    pages_total = validate_pages_total(data, errors)

    thumbnail_scan = as_page_map(data.get("thumbnail_scan"), "thumbnail_scan", errors)
    classification_review = as_page_map(
        data.get("classification_review") or [], "classification_review", errors
    )
    page_risks = as_page_map(data.get("page_risks"), "page_risks", errors)

    validate_page_coverage(pages_total, thumbnail_scan, "thumbnail_scan", errors)
    validate_page_coverage(pages_total, page_risks, "page_risks", errors)

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

    counts = {
        "page_risks": len(page_risks),
        "classification_review": len(classification_review),
    }
    return errors, warnings, counts


def validate_v2(data: dict[str, Any]) -> tuple[list[str], list[str], dict[str, int]]:
    errors: list[str] = []
    warnings: list[str] = []
    pages_total = validate_pages_total(data, errors)

    page_risks = as_page_map(data.get("page_risks"), "page_risks", errors)
    visual_notes = as_page_map(data.get("visual_page_notes") or [], "visual_page_notes", errors)
    final_pages = as_page_map(
        data.get("final_visual_review_pages") or [],
        "final_visual_review_pages",
        errors,
    )
    validate_page_coverage(pages_total, page_risks, "page_risks", errors)

    teaching_scan = data.get("teaching_image_scan") or {}
    if not isinstance(teaching_scan, dict):
        errors.append("teaching_image_scan must be a mapping")
        teaching_scan = {}
    confirmed = int_list(teaching_scan.get("confirmed"), "teaching_image_scan.confirmed", errors)
    uncertain = int_list(teaching_scan.get("uncertain"), "teaching_image_scan.uncertain", errors)
    teaching_pages = set(confirmed) | set(uncertain)

    for page, risk in page_risks.items():
        prefix = f"page_risks page {page}"
        risk_level = risk.get("risk_level")
        page_class = risk.get("page_class")
        if risk_level not in VALID_RISK:
            errors.append(f"{prefix}: invalid risk_level {risk_level!r}")
        if page_class not in VALID_PAGE_CLASS:
            errors.append(f"{prefix}: invalid page_class {page_class!r}")
        note_ref = risk.get("visual_note_ref")
        if note_ref is not None and note_ref not in visual_notes:
            errors.append(f"{prefix}: visual_note_ref {note_ref!r} has no visual_page_notes entry")

    for page, note in visual_notes.items():
        prefix = f"visual_page_notes page {page}"
        source = note.get("source")
        if source not in VALID_NOTE_SOURCE:
            errors.append(f"{prefix}: source must be one of {sorted(VALID_NOTE_SOURCE)}")
        if source == "comprehension_blocker" and not non_empty_string(note.get("blocker")):
            errors.append(f"{prefix}: blocker is required for comprehension_blocker notes")
        if not non_empty_string(note.get("rendered_page")):
            errors.append(f"{prefix}: rendered_page is required")
        if not non_empty_string(note.get("visual_observation")):
            errors.append(f"{prefix}: visual_observation is required")
        if not isinstance(note.get("provisional_concepts") or [], list):
            errors.append(f"{prefix}: provisional_concepts must be a list")
        if not non_empty_list(note.get("must_capture")):
            errors.append(f"{prefix}: must_capture must be a non-empty list")
        confidence = note.get("confidence")
        if confidence not in VALID_CONFIDENCE:
            errors.append(f"{prefix}: confidence must be one of {sorted(VALID_CONFIDENCE)}")

    for page, item in final_pages.items():
        prefix = f"final_visual_review_pages page {page}"
        source = item.get("source")
        if source not in VALID_NOTE_SOURCE:
            errors.append(f"{prefix}: source must be one of {sorted(VALID_NOTE_SOURCE)}")
        risk_level = item.get("risk_level")
        page_class = item.get("page_class")
        if risk_level not in VALID_RISK:
            errors.append(f"{prefix}: invalid risk_level {risk_level!r}")
        if page_class not in VALID_PAGE_CLASS:
            errors.append(f"{prefix}: invalid page_class {page_class!r}")
        if page not in visual_notes:
            errors.append(f"{prefix}: missing matching visual_page_notes entry")
        risk = page_risks.get(page)
        if risk:
            if risk.get("risk_level") != risk_level:
                errors.append(f"{prefix}: risk_level disagrees with page_risks")
            if risk.get("page_class") != page_class:
                errors.append(f"{prefix}: page_class disagrees with page_risks")

    missing_teaching = sorted(teaching_pages - set(final_pages))
    if missing_teaching:
        errors.append(
            "teaching_image_scan.confirmed + uncertain missing from final_visual_review_pages: "
            f"{missing_teaching[:20]}"
        )

    for page, risk in page_risks.items():
        if risk.get("risk_level") != "high":
            continue
        if page in final_pages:
            continue
        if not non_empty_string(risk.get("high_without_visual_review_reason")):
            errors.append(
                f"page_risks page {page}: high page must be in final_visual_review_pages "
                "or provide high_without_visual_review_reason"
            )

    extra_notes = sorted(set(visual_notes) - set(final_pages))
    if extra_notes:
        warnings.append(
            "visual_page_notes has page(s) not listed in final_visual_review_pages: "
            f"{extra_notes[:20]}"
        )

    counts = {
        "page_risks": len(page_risks),
        "visual_page_notes": len(visual_notes),
        "final_visual_review_pages": len(final_pages),
    }
    return errors, warnings, counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audit", help="docs/page-risk-<batch>.yaml")
    args = parser.parse_args()

    path = Path(args.audit)
    data = load_yaml(path)
    if not isinstance(data, dict):
        print("ERROR: audit root must be a mapping")
        return 1

    schema_version = data.get("schema_version", 1)
    if schema_version == 1:
        errors, warnings, counts = validate_v1(data)
    elif schema_version == 2:
        errors, warnings, counts = validate_v2(data)
    else:
        errors = [f"schema_version must be 1 or 2, got {schema_version!r}"]
        warnings = []
        counts = {}

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1

    count_summary = ", ".join(f"{key}={value}" for key, value in counts.items())
    print(
        f"OK: checked page-risk audit {path} "
        f"(schema_version={schema_version}, {count_summary}, warnings={len(warnings)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
