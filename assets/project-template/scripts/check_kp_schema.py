#!/usr/bin/env python3
"""Validate spec/knowledge-points.yaml."""

from __future__ import annotations

from collections import Counter
from typing import Any

from common import knowledge_points, workflow_state


VALID_STATUS = {"pool", "queued", "applied"}
VALID_NOTICE = {"none", "needed", "published"}
VALID_ACTION = {"new_chapter", "patch_chapter", "hold"}
VALID_ROLE = {
    "foundation", "mechanism", "method", "example",
    "formula", "pitfall", "exam_pattern",
}
VALID_CARD_TYPE = {"method", "example", "operation", "figure", "exam_tip"}
VALID_REVIEW_RISK = {"high", "medium", "low", "section_divider"}
VALID_PAGE_CLASS = {
    "process_diagram", "architecture_diagram", "state_machine",
    "comparison_table", "formula_derivation", "chart_or_plot",
    "code_or_command", "case_steps", "taxonomy", "table",
    "screenshot_or_scanned", "section_divider", "text_dense",
    "normal_text",
}
VALID_STRUCTURE_KIND = {
    "ordered_chain", "comparison", "state_machine", "formula",
    "architecture_diagram", "comparison_table", "taxonomy", "process",
    "case_steps", "table", "diagram", "code_or_command", "chart_or_plot",
}
VALID_HOLD_REASON = {
    "awaiting_followup", "bridging_undefined",
    "enrichment_only", "manual_review",
}
REQUIRED = {"id", "concept", "status"}


def validate_string_list(label: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return
    for j, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{label}[{j}] must be a non-empty string")


def validate_must_cover(kp_id: str, card_index: int, value: Any, errors: list[str]) -> None:
    label = f"{kp_id}: detail_cards[{card_index}].must_cover"
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return
    for j, item in enumerate(value):
        prefix = f"{label}[{j}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be a mapping")
            continue
        term = item.get("item")
        if not isinstance(term, str) or not term.strip():
            errors.append(f"{prefix}.item must be a non-empty string")
        aliases = item.get("aliases")
        if aliases is not None:
            validate_string_list(f"{prefix}.aliases", aliases, errors)
        role = item.get("role")
        if role is not None and (not isinstance(role, str) or not role.strip()):
            errors.append(f"{prefix}.role must be a non-empty string")
        deferred = item.get("deferred")
        if deferred is not None and not isinstance(deferred, bool):
            errors.append(f"{prefix}.deferred must be bool")
        if deferred:
            reason = item.get("defer_reason")
            if not isinstance(reason, str) or not reason.strip():
                errors.append(f"{prefix}.defer_reason is required when deferred=true")


def validate_detail_cards(kp_id: str, cards: Any, errors: list[str]) -> None:
    if cards is None:
        return
    if not isinstance(cards, list):
        errors.append(f"{kp_id}: detail_cards must be a list")
        return
    for i, card in enumerate(cards):
        if not isinstance(card, dict):
            errors.append(f"{kp_id}: detail_cards[{i}] must be a mapping")
            continue
        ctype = card.get("type")
        if ctype not in VALID_CARD_TYPE:
            errors.append(
                f"{kp_id}: detail_cards[{i}].type must be in {sorted(VALID_CARD_TYPE)}, got {ctype!r}"
            )
        deferred = card.get("deferred")
        if deferred is not None and not isinstance(deferred, bool):
            errors.append(f"{kp_id}: detail_cards[{i}].deferred must be bool")
        visual_reviewed = card.get("visual_reviewed")
        if visual_reviewed is not None and not isinstance(visual_reviewed, bool):
            errors.append(f"{kp_id}: detail_cards[{i}].visual_reviewed must be bool")
        risk = card.get("review_risk_level")
        if risk is not None and risk not in VALID_REVIEW_RISK:
            errors.append(
                f"{kp_id}: detail_cards[{i}].review_risk_level must be in "
                f"{sorted(VALID_REVIEW_RISK)}, got {risk!r}"
            )
        page_class = card.get("page_class")
        if page_class is not None and page_class not in VALID_PAGE_CLASS:
            errors.append(
                f"{kp_id}: detail_cards[{i}].page_class must be in "
                f"{sorted(VALID_PAGE_CLASS)}, got {page_class!r}"
            )
        structure_kind = card.get("structure_kind")
        if structure_kind is not None and structure_kind not in VALID_STRUCTURE_KIND:
            errors.append(
                f"{kp_id}: detail_cards[{i}].structure_kind must be in "
                f"{sorted(VALID_STRUCTURE_KIND)}, got {structure_kind!r}"
            )
        verified_items = card.get("verified_items")
        if verified_items is not None:
            validate_string_list(f"{kp_id}: detail_cards[{i}].verified_items", verified_items, errors)
        must_cover = card.get("must_cover")
        if must_cover is not None:
            validate_must_cover(kp_id, i, must_cover, errors)


def validate_links(kp_id: str, links: Any, errors: list[str]) -> None:
    if links is None:
        return
    if not isinstance(links, dict):
        errors.append(f"{kp_id}: links must be a mapping")
        return
    for key in ("prerequisites", "extends", "contrasts"):
        val = links.get(key)
        if val is None:
            continue
        if not isinstance(val, list):
            errors.append(f"{kp_id}: links.{key} must be a list")


def validate_retrieval_hooks(kp_id: str, hooks: Any, errors: list[str]) -> None:
    if hooks is None:
        return
    if not isinstance(hooks, dict):
        errors.append(f"{kp_id}: retrieval_hooks must be a mapping")
        return
    for key in ("local", "bridging"):
        val = hooks.get(key)
        if val is None:
            continue
        if not isinstance(val, list):
            errors.append(f"{kp_id}: retrieval_hooks.{key} must be a list")


def validate_queue(kp_id: str, queue: dict, errors: list[str]) -> None:
    action = queue.get("action")
    if action not in VALID_ACTION:
        errors.append(
            f"{kp_id}: queued KP must set queue.action in {sorted(VALID_ACTION)}, got {action!r}"
        )
        return
    if action in {"new_chapter", "patch_chapter"}:
        if not queue.get("target"):
            errors.append(f"{kp_id}: queued KP for {action} must set queue.target")
    elif action == "hold":
        reason = queue.get("reason")
        if reason not in VALID_HOLD_REASON:
            errors.append(
                f"{kp_id}: queue.action=hold requires queue.reason in "
                f"{sorted(VALID_HOLD_REASON)}, got {reason!r}"
            )


def main() -> int:
    kps = knowledge_points()
    state = workflow_state()
    current_job = state.get("current_job") or {}
    current_job_id = current_job.get("id")

    errors: list[str] = []
    warnings: list[str] = []
    ids = [kp.get("id") for kp in kps]
    for kp_id, count in Counter(ids).items():
        if kp_id and count > 1:
            errors.append(f"{kp_id}: duplicate id")

    for idx, kp in enumerate(kps, start=1):
        kp_id = str(kp.get("id", f"<item-{idx}>"))
        missing = sorted(field for field in REQUIRED if field not in kp or kp.get(field) in (None, ""))
        if missing:
            errors.append(f"{kp_id}: missing required fields {', '.join(missing)}")
            continue

        status = kp.get("status")
        if status not in VALID_STATUS:
            errors.append(f"{kp_id}: invalid status {status!r}")

        notice = kp.get("reader_notice", "none")
        if notice not in VALID_NOTICE:
            errors.append(f"{kp_id}: invalid reader_notice {notice!r}")

        role = kp.get("role")
        if role is not None and role not in VALID_ROLE:
            errors.append(f"{kp_id}: invalid role {role!r}; must be in {sorted(VALID_ROLE)}")

        core = kp.get("core")
        if core is not None and not isinstance(core, bool):
            errors.append(f"{kp_id}: core must be bool, got {type(core).__name__}")

        applied_to = kp.get("applied_to")
        if applied_to is not None and not isinstance(applied_to, list):
            errors.append(f"{kp_id}: applied_to must be a list (got {type(applied_to).__name__})")

        if status == "pool":
            if kp.get("queue"):
                errors.append(f"{kp_id}: pool KP must not have queue field (use queue.action=hold via queued status)")
        elif status == "queued":
            queue = kp.get("queue")
            if not isinstance(queue, dict):
                errors.append(f"{kp_id}: queued KP must have queue mapping")
            else:
                validate_queue(kp_id, queue, errors)
        elif status == "applied":
            if kp.get("queue"):
                warnings.append(f"{kp_id}: applied KP still has queue field (should be cleared)")
            if not applied_to:
                warnings.append(f"{kp_id}: applied KP should set applied_to")

        if kp.get("locked_by") and kp.get("locked_by") != current_job_id:
            warnings.append(f"{kp_id}: locked_by={kp.get('locked_by')} but current_job is {current_job_id!r}")

        validate_detail_cards(kp_id, kp.get("detail_cards"), errors)
        validate_links(kp_id, kp.get("links"), errors)
        validate_retrieval_hooks(kp_id, kp.get("retrieval_hooks"), errors)

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print(f"OK: checked {len(kps)} knowledge point(s) ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
