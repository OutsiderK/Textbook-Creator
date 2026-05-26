#!/usr/bin/env python3
"""Validate Stage C visual-plan contracts against chapter artifacts."""

from __future__ import annotations

import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml

from common import ROOT, knowledge_points, load_yaml, rel


CALLOUT_LABELS = {"核心判断", "易错点", "常见误区", "思维停顿"}


def split_frontmatter(text: str) -> tuple[dict[str, Any], str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    front = text[4:end]
    body = text[end + 5 :]
    return yaml.safe_load(front) or {}, body


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text.casefold())


def contains_candidate(haystack: str, candidate: str) -> bool:
    candidate = str(candidate or "").strip()
    if not candidate:
        return False
    raw = haystack.casefold()
    if candidate.casefold() in raw:
        return True
    if normalize(candidate) in normalize(raw):
        return True
    return compact(candidate) in compact(raw)


def require_markdown_parser() -> Any:
    try:
        from markdown_it import MarkdownIt
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "missing dependency: markdown-it-py. Install it before running visual checks; "
            "this script does not fall back to regex-only Markdown parsing."
        ) from exc
    return MarkdownIt("commonmark").enable("table")


def parse_markdown(body: str) -> dict[str, Any]:
    md = require_markdown_parser()
    tokens = md.parse(body)
    tables: list[dict[str, Any]] = []
    callouts: list[str] = []
    ordered_items: list[str] = []

    in_table = False
    rows: list[list[str]] = []
    current_row: list[str] | None = None
    current_cell: list[str] | None = None
    in_ordered_list = False
    list_depth = 0
    in_blockquote = False
    blockquote_parts: list[str] = []

    for token in tokens:
        if token.type == "table_open":
            in_table = True
            rows = []
        elif token.type == "table_close":
            if rows:
                tables.append({"headers": rows[0], "rows": rows[1:], "text": table_text(rows)})
            in_table = False
        elif in_table and token.type == "tr_open":
            current_row = []
        elif in_table and token.type == "tr_close":
            if current_row is not None:
                rows.append(current_row)
            current_row = None
        elif in_table and token.type in {"th_open", "td_open"}:
            current_cell = []
        elif in_table and token.type in {"th_close", "td_close"}:
            if current_row is not None and current_cell is not None:
                current_row.append(" ".join(current_cell).strip())
            current_cell = None
        elif in_table and token.type == "inline" and current_cell is not None:
            current_cell.append(token.content)

        if token.type == "ordered_list_open":
            in_ordered_list = True
            list_depth += 1
        elif token.type == "ordered_list_close":
            list_depth -= 1
            in_ordered_list = list_depth > 0
        elif in_ordered_list and token.type == "inline":
            ordered_items.append(token.content)

        if token.type == "blockquote_open":
            in_blockquote = True
            blockquote_parts = []
        elif token.type == "blockquote_close":
            text = " ".join(part.strip() for part in blockquote_parts if part.strip())
            if any(f"**{label}**" in text or f"**{label}**:" in text or f"**{label}**：" in text for label in CALLOUT_LABELS):
                callouts.append(text)
            in_blockquote = False
        elif in_blockquote and token.type == "inline":
            blockquote_parts.append(token.content)

    return {"tables": tables, "callouts": callouts, "ordered_items": ordered_items}


def table_text(rows: list[list[str]]) -> str:
    return "\n".join(" | ".join(cell for cell in row) for row in rows)


def extract_formula_blocks(body: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    lines = body.splitlines()
    start: int | None = None
    content: list[str] = []
    for idx, line in enumerate(lines):
        if line.strip() == "$$":
            if start is None:
                start = idx
                content = [line]
            else:
                content.append(line)
                blocks.append({"text": "\n".join(content), "start": start, "end": idx})
                start = None
                content = []
        elif start is not None:
            content.append(line)
    return blocks


def has_adjacent_variable_table(body: str, formula: dict[str, Any]) -> bool:
    lines = body.splitlines()
    window = lines[formula["end"] + 1 : formula["end"] + 12]
    joined = "\n".join(window)
    return ("| 符号 |" in joined or "| 变量 |" in joined or "| Symbol |" in joined) and (
        "| 含义 |" in joined or "| 意义 |" in joined or "| Meaning |" in joined
    )


def target_label(path: Path) -> str:
    return rel(path) if path.is_absolute() and ROOT in path.parents else path.as_posix()


def visual_plan_path_for_target(target: str) -> Path:
    stem = os.path.splitext(os.path.basename(target))[0]
    return ROOT / "spec" / "visual-plans" / f"{stem}.yaml"


def load_overrides() -> dict[str, Any]:
    return load_yaml("spec/quality-overrides.yaml", {"version": 1, "legacy_chapters": []})


def is_legacy(target: str) -> bool:
    overrides = load_overrides()
    return target in set(str(item) for item in overrides.get("legacy_chapters", []) or [])


def coverage_ids(path: Path) -> tuple[list[str], str, list[str]]:
    text = path.read_text(encoding="utf-8")
    parsed = split_frontmatter(text)
    if not parsed:
        return [], text, [f"{target_label(path)}: missing YAML front matter"]
    front, body = parsed
    coverage = front.get("coverage", [])
    if not isinstance(coverage, list):
        return [], body, [f"{target_label(path)}: front matter coverage must be a list"]
    return [str(item) for item in coverage], body, []


def card_needs_plan(card: dict[str, Any]) -> bool:
    if card.get("deferred") is True:
        return False
    must_cover = card.get("must_cover") or []
    return bool(card.get("visual_reviewed") is True or card.get("type") == "figure" or must_cover)


def card_ref(card: dict[str, Any]) -> dict[str, Any]:
    return {"source_slide": card.get("source_slide"), "card_type": card.get("type")}


def ref_key(kp_id: str, ref: dict[str, Any]) -> tuple[str, str, str]:
    return (str(kp_id), str(ref.get("source_slide")), str(ref.get("card_type")))


def same_ref(card: dict[str, Any], ref: dict[str, Any]) -> bool:
    return str(card.get("source_slide")) == str(ref.get("source_slide")) and str(card.get("type")) == str(ref.get("card_type"))


def item_candidates(item: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    value = item.get("item")
    if isinstance(value, str):
        candidates.append(value)
    aliases = item.get("aliases") or []
    if isinstance(aliases, list):
        candidates.extend(alias for alias in aliases if isinstance(alias, str))
    return candidates


def card_must_cover(card: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in card.get("must_cover") or []:
        if isinstance(item, dict) and item.get("deferred") is not True:
            items.append(item)
    return items


def svg_text(path: Path) -> str:
    root = ET.parse(path).getroot()
    chunks: list[str] = []
    for elem in root.iter():
        tag = elem.tag.rsplit("}", 1)[-1]
        if tag == "text":
            chunks.append("".join(elem.itertext()))
    return "\n".join(chunks)


def item_refs(item: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if isinstance(item.get("group"), list):
        for entry in item["group"]:
            if isinstance(entry, dict):
                refs.append(entry)
    elif isinstance(item.get("card_ref"), dict):
        refs.append({"kp": item.get("kp"), "card_ref": item.get("card_ref")})
    return refs


def representation_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def carrier_for_representation(
    rep: str,
    output: dict[str, Any],
    chapter_body: str,
    chapter_text: str,
    parsed: dict[str, Any],
    formula_blocks: list[dict[str, Any]],
    errors: list[str],
    label: str,
    item_id: str,
) -> str:
    if rep == "svg":
        svg_path = output.get("svg")
        if not isinstance(svg_path, str) or not svg_path.strip():
            errors.append(f"{label}: {item_id}: representation svg missing output.svg")
            return ""
        path = ROOT / svg_path
        if not path.exists():
            errors.append(f"{label}: {item_id}: SVG file does not exist: {svg_path}")
            return ""
        if svg_path not in chapter_text:
            errors.append(f"{label}: {item_id}: chapter does not embed output.svg {svg_path}")
        try:
            return svg_text(path)
        except Exception as exc:
            errors.append(f"{label}: {item_id}: cannot parse SVG {svg_path}: {exc}")
            return ""

    if rep == "table":
        table_decl = output.get("table")
        headers = table_decl.get("headers") if isinstance(table_decl, dict) else None
        if not isinstance(headers, list) or not headers:
            errors.append(f"{label}: {item_id}: representation table missing output.table.headers")
            return ""
        for table in parsed["tables"]:
            table_headers = " ".join(table["headers"])
            if all(contains_candidate(table_headers, str(header)) for header in headers):
                return table["text"]
        errors.append(f"{label}: {item_id}: no Markdown table matches headers {headers}")
        return ""

    if rep == "formula":
        formula = output.get("formula")
        if not isinstance(formula, str) or not formula.strip():
            errors.append(f"{label}: {item_id}: representation formula missing output.formula")
            return ""
        for block in formula_blocks:
            if formula.strip() in block["text"]:
                if not has_adjacent_variable_table(chapter_body, block):
                    errors.append(f"{label}: {item_id}: formula output is not adjacent to a variable table")
                lines = chapter_body.splitlines()
                adjacent = "\n".join(lines[block["end"] + 1 : block["end"] + 12])
                return f"{block['text']}\n{adjacent}"
        errors.append(f"{label}: {item_id}: output.formula not found as a $$ block substring")
        return ""

    if rep == "steps":
        steps = output.get("steps")
        if not isinstance(steps, list) or not steps:
            errors.append(f"{label}: {item_id}: representation steps missing output.steps")
            return ""
        ordered_text = "\n".join(parsed["ordered_items"])
        for step in steps:
            if not contains_candidate(ordered_text, str(step)):
                errors.append(f"{label}: {item_id}: ordered list does not contain step {step!r}")
        return ordered_text

    if rep == "callout":
        callout = output.get("callout")
        if not isinstance(callout, str) or not callout.strip():
            errors.append(f"{label}: {item_id}: representation callout missing output.callout")
            return ""
        for block in parsed["callouts"]:
            if callout in block:
                return block
        errors.append(f"{label}: {item_id}: no callout contains output.callout {callout!r}")
        return ""

    if rep == "prose":
        prose = output.get("prose")
        if not isinstance(prose, str) or not prose.strip():
            errors.append(f"{label}: {item_id}: representation prose missing output.prose")
            return ""
        if prose not in chapter_body:
            errors.append(f"{label}: {item_id}: chapter body does not contain output.prose {prose!r}")
        return chapter_body

    errors.append(f"{label}: {item_id}: unknown representation {rep!r}")
    return ""


def check_items_cover_must_cover(label: str, item_id: str, carrier_texts: list[str], must_cover: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    joined = "\n".join(carrier_texts)
    for item in must_cover:
        candidates = item_candidates(item)
        if not candidates:
            errors.append(f"{label}: {item_id}: must_cover item has no item or aliases")
            continue
        if not any(contains_candidate(joined, candidate) for candidate in candidates):
            errors.append(f"{label}: {item_id}: declared representation does not cover must_cover {candidates[0]!r}")
    return errors


def check_chapter(path: Path, kp_by_id: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    label = target_label(path)
    if is_legacy(label):
        return [], [f"SKIP: {label} is in legacy_chapters"]

    coverage, body, errors = coverage_ids(path)
    if errors:
        return errors, []
    chapter_text = path.read_text(encoding="utf-8")
    parsed = parse_markdown(body)
    formula_blocks = extract_formula_blocks(body)

    plan_path = visual_plan_path_for_target(label)
    if not plan_path.exists():
        return [f"{label}: missing visual plan {rel(plan_path)}"], []
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
    if plan.get("target") != label:
        errors.append(f"{label}: visual plan target must be {label!r}, got {plan.get('target')!r}")
    if plan.get("status") != "final":
        errors.append(f"{label}: visual plan status must be 'final' before finish")

    required: dict[tuple[str, str, str], tuple[str, dict[str, Any]]] = {}
    for kp_id in coverage:
        kp = kp_by_id.get(kp_id)
        if not kp:
            continue
        for card in kp.get("detail_cards") or []:
            if isinstance(card, dict) and card_needs_plan(card):
                key = ref_key(kp_id, card_ref(card))
                required[key] = (kp_id, card)

    planned_keys: set[tuple[str, str, str]] = set()
    items = plan.get("items") or []
    if not isinstance(items, list):
        errors.append(f"{label}: visual plan items must be a list")
        return errors, []

    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{label}: visual plan items[{idx}] must be a mapping")
            continue
        item_id = str(item.get("id") or f"items[{idx}]")
        reps = representation_list(item.get("representation"))
        if not reps:
            errors.append(f"{label}: {item_id}: missing representation")
            continue
        output = item.get("output")
        if not isinstance(output, dict):
            errors.append(f"{label}: {item_id}: missing output mapping")
            output = {}
        if "prose" in reps and not str(item.get("reason") or "").strip():
            errors.append(f"{label}: {item_id}: representation prose requires non-empty reason")
        if item.get("group") and not str(item.get("reason") or "").strip():
            errors.append(f"{label}: {item_id}: grouped cards require non-empty reason")

        referenced_cards: list[dict[str, Any]] = []
        for ref_entry in item_refs(item):
            kp_id = str(ref_entry.get("kp") or "")
            ref = ref_entry.get("card_ref")
            if not kp_id or not isinstance(ref, dict):
                errors.append(f"{label}: {item_id}: each ref needs kp and card_ref")
                continue
            kp = kp_by_id.get(kp_id)
            if not kp:
                errors.append(f"{label}: {item_id}: unknown KP {kp_id}")
                continue
            matches = [card for card in kp.get("detail_cards") or [] if isinstance(card, dict) and same_ref(card, ref)]
            if len(matches) != 1:
                errors.append(
                    f"{label}: {item_id}: card_ref {ref} for {kp_id} matched {len(matches)} card(s); expected exactly 1"
                )
                continue
            key = ref_key(kp_id, ref)
            planned_keys.add(key)
            referenced_cards.append(matches[0])

        carrier_texts: list[str] = []
        for rep in reps:
            carrier_texts.append(
                carrier_for_representation(
                    rep, output, body, chapter_text, parsed, formula_blocks, errors, label, item_id
                )
            )

        must_cover: list[dict[str, Any]] = []
        for card in referenced_cards:
            must_cover.extend(card_must_cover(card))
        errors.extend(check_items_cover_must_cover(label, item_id, carrier_texts, must_cover))

    missing = sorted(required_key for required_key in required if required_key not in planned_keys)
    for key in missing:
        kp_id, card = required[key]
        errors.append(f"{label}: missing visual-plan item for {kp_id} card_ref={card_ref(card)}")

    return errors, []


def main(argv: list[str]) -> int:
    if argv:
        chapters = [Path(arg) if Path(arg).is_absolute() else ROOT / arg for arg in argv]
    else:
        chapters = sorted((ROOT / "book").glob("ch*.md"))

    kp_by_id = {str(kp.get("id")): kp for kp in knowledge_points() if kp.get("id")}
    all_errors: list[str] = []
    all_warnings: list[str] = []

    try:
        for chapter in chapters:
            if not chapter.exists():
                all_errors.append(f"{chapter}: file does not exist")
                continue
            errors, warnings = check_chapter(chapter, kp_by_id)
            all_errors.extend(errors)
            all_warnings.extend(warnings)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 1

    for warning in all_warnings:
        print(f"WARNING: {warning}")
    for error in all_errors:
        print(f"ERROR: {error}")
    if all_errors:
        return 1
    print(f"OK: visual assets checked for {len(chapters)} chapter(s) ({len(all_warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
