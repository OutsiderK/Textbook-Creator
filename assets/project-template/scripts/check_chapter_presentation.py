#!/usr/bin/env python3
"""Validate Stage C presentation floor without judging aesthetics."""

from __future__ import annotations

import os
import re
import sys
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


def require_markdown_parser() -> Any:
    try:
        from markdown_it import MarkdownIt
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "missing dependency: markdown-it-py. Install it before running presentation checks; "
            "this script does not fall back to regex-only Markdown parsing."
        ) from exc
    return MarkdownIt("commonmark").enable("table")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text.casefold())


def contains_candidate(haystack: str, candidate: str) -> bool:
    candidate = str(candidate or "").strip()
    if not candidate:
        return False
    raw = haystack.casefold()
    return candidate.casefold() in raw or normalize(candidate) in normalize(raw) or compact(candidate) in compact(raw)


def parse_markdown(body: str) -> dict[str, Any]:
    md = require_markdown_parser()
    tokens = md.parse(body)
    tables = 0
    figures = 0
    code_blocks = 0
    headings_h2 = 0
    callouts: list[str] = []
    ordered_items: list[str] = []

    in_blockquote = False
    blockquote_parts: list[str] = []
    in_ordered_list = False
    list_depth = 0

    for token in tokens:
        if token.type == "table_open":
            tables += 1
        elif token.type == "image":
            figures += 1
        elif token.type in {"fence", "code_block"}:
            code_blocks += 1
        elif token.type == "heading_open" and token.tag == "h2":
            headings_h2 += 1

        if token.type == "ordered_list_open":
            in_ordered_list = True
            list_depth += 1
        elif token.type == "ordered_list_close":
            list_depth -= 1
            in_ordered_list = list_depth > 0
        elif in_ordered_list and token.type == "inline":
            ordered_items.append(token.content)

        if token.type == "inline":
            for child in token.children or []:
                if child.type == "image":
                    figures += 1

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

    return {
        "tables": tables,
        "figures": figures,
        "code_blocks": code_blocks,
        "headings_h2": headings_h2,
        "callouts": callouts,
        "ordered_items": ordered_items,
    }


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


def load_overrides() -> dict[str, Any]:
    return load_yaml("spec/quality-overrides.yaml", {"version": 1, "legacy_chapters": []})


def target_label(path: Path) -> str:
    return rel(path) if path.is_absolute() and ROOT in path.parents else path.as_posix()


def is_legacy(target: str) -> bool:
    overrides = load_overrides()
    return target in set(str(item) for item in overrides.get("legacy_chapters", []) or [])


def coverage_and_body(path: Path) -> tuple[list[str], str, list[str]]:
    text = path.read_text(encoding="utf-8")
    parsed = split_frontmatter(text)
    if not parsed:
        return [], text, [f"{target_label(path)}: missing YAML front matter"]
    front, body = parsed
    coverage = front.get("coverage", [])
    if not isinstance(coverage, list):
        return [], body, [f"{target_label(path)}: front matter coverage must be a list"]
    return [str(item) for item in coverage], body, []


def visual_plan_path_for_target(target: str) -> Path:
    stem = os.path.splitext(os.path.basename(target))[0]
    return ROOT / "spec" / "visual-plans" / f"{stem}.yaml"


def summary_candidates(summary: str) -> list[str]:
    summary = summary.strip()
    if not summary:
        return []
    candidates = [summary]
    highlighted = re.findall(r"==(.+?)==", summary)
    candidates.extend(highlighted)
    pieces = re.split(r"[，。；;:：、,()\s]+", summary)
    candidates.extend(piece for piece in pieces if len(piece) >= 4)
    return list(dict.fromkeys(candidates))


def highlighted_text(body: str) -> str:
    return "\n".join(re.findall(r"==(.+?)==", body, flags=re.S))


def exercise_text(body: str) -> str:
    marker = "## 练习"
    idx = body.find(marker)
    return body[idx:] if idx != -1 else ""


def exam_tip_consumed(card: dict[str, Any], body: str, callouts: list[str]) -> bool:
    summary = str(card.get("summary") or "")
    candidates = summary_candidates(summary)
    if not candidates:
        return True
    highlighted = highlighted_text(body)
    for candidate in candidates:
        if contains_candidate(highlighted, candidate) or contains_candidate(candidate, highlighted):
            return True
    callout_text = "\n".join(callouts)
    for candidate in candidates:
        if contains_candidate(callout_text, candidate):
            return True
    exercises = exercise_text(body)
    for candidate in candidates:
        if contains_candidate(exercises, candidate):
            return True
    return False


def visual_plan_callouts_required(target: str) -> list[str]:
    plan_path = visual_plan_path_for_target(target)
    if not plan_path.exists():
        return []
    plan = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
    required: list[str] = []
    for item in plan.get("items") or []:
        if not isinstance(item, dict):
            continue
        reps = item.get("representation")
        if isinstance(reps, str):
            reps = [reps]
        if isinstance(reps, list) and "callout" in reps:
            output = item.get("output") or {}
            value = output.get("callout") if isinstance(output, dict) else None
            if isinstance(value, str) and value.strip():
                required.append(value)
    return required


def long_plain_paragraph_warnings(label: str, body: str) -> list[str]:
    warnings: list[str] = []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    long_run = 0
    for paragraph in paragraphs:
        is_structured = paragraph.startswith(("|", ">", "```", "$$", "!", "#")) or re.match(r"^\d+\.\s", paragraph)
        if not is_structured and len(paragraph) > 220:
            long_run += 1
        else:
            long_run = 0
        if long_run >= 3:
            warnings.append(f"{label}: three or more long plain-text paragraphs in a row")
            break
    return warnings


def check_chapter(path: Path, kp_by_id: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    label = target_label(path)
    if is_legacy(label):
        return [], [f"SKIP: {label} is in legacy_chapters"]

    coverage, body, errors = coverage_and_body(path)
    if errors:
        return errors, []

    parsed = parse_markdown(body)
    warnings: list[str] = []

    formula_blocks = extract_formula_blocks(body)
    for block in formula_blocks:
        if not has_adjacent_variable_table(body, block):
            errors.append(f"{label}: formula block at line {block['start'] + 1} is not adjacent to a variable table")

    for kp_id in coverage:
        kp = kp_by_id.get(kp_id)
        if not kp:
            continue
        for card in kp.get("detail_cards") or []:
            if not isinstance(card, dict) or card.get("deferred") is True:
                continue
            if card.get("type") == "exam_tip" and not exam_tip_consumed(card, body, parsed["callouts"]):
                errors.append(f"{label}: exam_tip from {kp_id} was not consumed with ==highlight==, callout, or exercise")

    callout_text = "\n".join(parsed["callouts"])
    for required in visual_plan_callouts_required(label):
        if required not in callout_text:
            errors.append(f"{label}: visual plan declares callout output not found in chapter: {required!r}")

    if parsed["tables"] + parsed["figures"] == 0:
        warnings.append(f"{label}: no figure or Markdown table found")
    if not parsed["callouts"]:
        warnings.append(f"{label}: no recognized callout found")
    if parsed["headings_h2"] > 5 and parsed["tables"] + parsed["figures"] == 0:
        warnings.append(f"{label}: many second-level sections but no figure/table scan structure")
    if len(parsed["callouts"]) > 8:
        warnings.append(f"{label}: many callouts ({len(parsed['callouts'])}); check reading rhythm")
    warnings.extend(long_plain_paragraph_warnings(label, body))

    return errors, warnings


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
    print(f"OK: chapter presentation checked for {len(chapters)} chapter(s) ({len(all_warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
