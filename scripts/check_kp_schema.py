#!/usr/bin/env python3
"""Validate spec/knowledge-points.yaml structurally.

Usage:
    python3 check_kp_schema.py <project-root>

Exits:
    0 — all KPs valid
    1 — at least one hard validation error
    2 — script setup error (missing file, etc.)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed.", file=sys.stderr)
    sys.exit(2)


REQUIRED_FIELDS = {"id", "concept", "source", "status", "role", "core"}
VALID_STATUS = {"pool", "queued", "applied"}
VALID_READER_NOTICE = {"none", "needed", "published"}
VALID_ROLE = {
    "foundation", "mechanism", "method", "example",
    "formula", "pitfall", "exam_pattern",
}
VALID_DETAIL_TYPE = {"method", "example", "operation", "figure", "exam_tip"}
VALID_POOL_REASON = {
    "awaiting_followup", "bridging_undefined",
    "enrichment_only", "manual_review",
}
VALID_ACTION = {"new_chapter", "patch_chapter"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root")
    args = parser.parse_args()

    project_root = Path(args.project_root)
    kp_path = project_root / "spec" / "knowledge-points.yaml"
    if not kp_path.exists():
        print(f"ERROR: {kp_path} not found", file=sys.stderr)
        sys.exit(2)

    try:
        data = yaml.safe_load(kp_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"✗ YAML parse error: {e}", file=sys.stderr)
        sys.exit(1)

    if data is None:
        print("✓ knowledge-points.yaml is empty (no KPs to validate)")
        sys.exit(0)

    if isinstance(data, list):
        kps = data
    elif isinstance(data, dict):
        kps = data.get("knowledge_points", []) or []
    else:
        print(f"✗ unexpected top-level type: {type(data).__name__}", file=sys.stderr)
        sys.exit(1)

    errors: list[str] = []
    seen_ids: dict[str, int] = {}

    for i, kp in enumerate(kps):
        prefix = f"KP[{i}]"
        if not isinstance(kp, dict):
            errors.append(f"{prefix}: not a mapping")
            continue

        kp_id = kp.get("id", "<no-id>")
        prefix = f"KP[{i}] {kp_id}"

        # Required fields
        missing = REQUIRED_FIELDS - set(kp.keys())
        if missing:
            errors.append(f"{prefix}: missing required fields: {sorted(missing)}")

        # Duplicate id
        if isinstance(kp_id, str) and kp_id != "<no-id>":
            if kp_id in seen_ids:
                errors.append(f"{prefix}: duplicate id (also at index {seen_ids[kp_id]})")
            else:
                seen_ids[kp_id] = i

        # Enum checks
        status = kp.get("status")
        if status not in VALID_STATUS:
            errors.append(f"{prefix}: invalid status '{status}' (expected one of {sorted(VALID_STATUS)})")

        role = kp.get("role")
        if role not in VALID_ROLE:
            errors.append(f"{prefix}: invalid role '{role}' (expected one of {sorted(VALID_ROLE)})")

        core = kp.get("core")
        if not isinstance(core, bool):
            errors.append(f"{prefix}: core must be boolean")

        reader_notice = kp.get("reader_notice")
        if reader_notice is not None and reader_notice not in VALID_READER_NOTICE:
            errors.append(f"{prefix}: invalid reader_notice '{reader_notice}'")

        # Source format
        source = kp.get("source")
        if not isinstance(source, list):
            errors.append(f"{prefix}: source must be a list of {{ppt, slides}} mappings")
        else:
            for j, s in enumerate(source):
                if not isinstance(s, dict):
                    errors.append(f"{prefix}: source[{j}] not a mapping")
                    continue
                if "ppt" not in s:
                    errors.append(f"{prefix}: source[{j}] missing 'ppt'")
                slides = s.get("slides")
                if slides is not None and not isinstance(slides, list):
                    errors.append(f"{prefix}: source[{j}].slides must be a list")

        # Detail cards
        detail_cards = kp.get("detail_cards", [])
        if not isinstance(detail_cards, list):
            errors.append(f"{prefix}: detail_cards must be a list")
        else:
            for j, card in enumerate(detail_cards):
                if not isinstance(card, dict):
                    errors.append(f"{prefix}: detail_cards[{j}] not a mapping")
                    continue
                if card.get("type") not in VALID_DETAIL_TYPE:
                    errors.append(
                        f"{prefix}: detail_cards[{j}].type invalid: '{card.get('type')}'"
                    )
                if "summary" not in card:
                    errors.append(f"{prefix}: detail_cards[{j}] missing 'summary'")

        # Status-dependent fields
        if status == "queued":
            action = kp.get("action")
            if action not in VALID_ACTION:
                errors.append(f"{prefix}: queued KP must have action in {sorted(VALID_ACTION)}")
            if not kp.get("applied_to"):
                errors.append(f"{prefix}: queued KP must have applied_to")
            # patch_chapter implies reader_notice=needed; new_chapter implies none
            if action == "patch_chapter" and kp.get("reader_notice") != "needed":
                errors.append(
                    f"{prefix}: action=patch_chapter requires reader_notice='needed' (got '{kp.get('reader_notice')}')"
                )
            if action == "new_chapter" and kp.get("reader_notice") not in (None, "none"):
                errors.append(
                    f"{prefix}: action=new_chapter requires reader_notice='none' (got '{kp.get('reader_notice')}')"
                )

        if status == "applied":
            if not kp.get("applied_to"):
                errors.append(f"{prefix}: applied KP must have applied_to")
            # action field should not exist after applied (cleared on stage exit)
            if "action" in kp:
                errors.append(f"{prefix}: applied KP should not retain 'action' field")

        if status == "pool":
            pool_reason = kp.get("pool_reason")
            if pool_reason is not None and pool_reason not in VALID_POOL_REASON:
                errors.append(
                    f"{prefix}: invalid pool_reason '{pool_reason}'"
                )

        # Links integrity (forward pass; verify later)
        links = kp.get("links", {}) or {}
        if not isinstance(links, dict):
            errors.append(f"{prefix}: links must be a mapping")
        else:
            for rel in ("prerequisites", "extends", "contrasts"):
                rel_ids = links.get(rel, []) or []
                if not isinstance(rel_ids, list):
                    errors.append(f"{prefix}: links.{rel} must be a list")

    # Cross-reference pass: link targets must exist
    all_ids = set(seen_ids.keys())
    for i, kp in enumerate(kps):
        if not isinstance(kp, dict):
            continue
        kp_id = kp.get("id", "<no-id>")
        prefix = f"KP[{i}] {kp_id}"
        links = kp.get("links", {}) or {}
        if isinstance(links, dict):
            for rel in ("prerequisites", "extends", "contrasts"):
                for ref in links.get(rel, []) or []:
                    if ref not in all_ids:
                        errors.append(f"{prefix}: links.{rel} references unknown id '{ref}'")

    if errors:
        for e in errors:
            print(f"✗ {e}")
        print(f"\n{len(errors)} error(s) in {len(kps)} KP(s)")
        sys.exit(1)

    print(f"✓ knowledge-points.yaml OK ({len(kps)} KPs)")
    sys.exit(0)


if __name__ == "__main__":
    main()
