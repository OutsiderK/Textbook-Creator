#!/usr/bin/env python3
"""Validate that visual must-cover detail items landed in chapter content."""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml

from common import ROOT, knowledge_points, rel


def split_frontmatter(text: str) -> tuple[dict[str, Any], str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    front = text[4:end]
    body = text[end + 5 :]
    data = yaml.safe_load(front) or {}
    return data, body


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.casefold()).strip()


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text.casefold())


def candidate_matches(candidate: str, haystack_raw: str, haystack_norm: str, haystack_compact: str) -> bool:
    candidate = candidate.strip()
    if not candidate:
        return False
    lowered = candidate.casefold()
    if lowered in haystack_raw:
        return True
    norm = normalize(candidate)
    if norm and norm in haystack_norm:
        return True
    comp = compact(candidate)
    return bool(comp and comp in haystack_compact)


def chapter_prefix(path: Path) -> str:
    match = re.match(r"(ch\d+)", path.stem)
    return match.group(1) if match else path.stem


def svg_text(path: Path) -> str:
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return ""
    chunks: list[str] = []
    for elem in root.iter():
        tag = elem.tag.rsplit("}", 1)[-1]
        if tag == "text":
            chunks.append("".join(elem.itertext()))
    return "\n".join(chunks)


def support_text_for_chapter(path: Path) -> str:
    text_parts: list[str] = []
    chapter_text = path.read_text(encoding="utf-8")
    parsed = split_frontmatter(chapter_text)
    text_parts.append(parsed[1] if parsed else chapter_text)

    prefix = chapter_prefix(path)

    supplement_dir = ROOT / "book" / "supplements"
    if supplement_dir.exists():
        for supplement in sorted(supplement_dir.glob(f"{prefix}-*.md")):
            text_parts.append(supplement.read_text(encoding="utf-8"))

    figure_dir = ROOT / "assets" / "figures"
    if figure_dir.exists():
        for figure in sorted(figure_dir.glob(f"{prefix}-*.svg")):
            text = svg_text(figure)
            if text:
                text_parts.append(text)

    return "\n".join(text_parts)


def coverage_ids(path: Path) -> tuple[list[str], list[str]]:
    text = path.read_text(encoding="utf-8")
    parsed = split_frontmatter(text)
    if not parsed:
        return [], [f"{rel(path)}: missing YAML front matter"]
    data, _body = parsed
    coverage = data.get("coverage", [])
    if coverage is None:
        return [], []
    if not isinstance(coverage, list):
        return [], [f"{rel(path)}: front matter coverage must be a list"]
    return [str(item) for item in coverage], []


def item_candidates(item: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    term = item.get("item")
    if isinstance(term, str):
        candidates.append(term)
    aliases = item.get("aliases") or []
    if isinstance(aliases, list):
        candidates.extend(alias for alias in aliases if isinstance(alias, str))
    return candidates


def check_chapter(path: Path, kp_by_id: dict[str, dict[str, Any]]) -> tuple[list[str], list[str], int, int]:
    errors: list[str] = []
    warnings: list[str] = []
    coverage, coverage_errors = coverage_ids(path)
    errors.extend(coverage_errors)
    if errors:
        return errors, warnings, 0, 0

    support_raw = support_text_for_chapter(path).casefold()
    support_norm = normalize(support_raw)
    support_compact = compact(support_raw)

    checked = 0
    deferred = 0
    chapter_label = rel(path)

    for kp_id in coverage:
        kp = kp_by_id.get(kp_id)
        if not kp:
            continue
        cards = kp.get("detail_cards") or []
        if not isinstance(cards, list):
            continue
        for card_index, card in enumerate(cards):
            if not isinstance(card, dict):
                continue
            if card.get("deferred") is True:
                deferred += 1
                continue
            must_cover = card.get("must_cover") or []
            if not isinstance(must_cover, list):
                continue
            for item_index, item in enumerate(must_cover):
                if not isinstance(item, dict):
                    continue
                if item.get("deferred") is True:
                    deferred += 1
                    reason = item.get("defer_reason")
                    if not isinstance(reason, str) or not reason.strip():
                        errors.append(
                            f"{chapter_label}: {kp_id} detail_cards[{card_index}].must_cover[{item_index}] "
                            "is deferred but missing defer_reason"
                        )
                    continue
                candidates = item_candidates(item)
                if not candidates:
                    errors.append(
                        f"{chapter_label}: {kp_id} detail_cards[{card_index}].must_cover[{item_index}] "
                        "has no item or aliases"
                    )
                    continue
                checked += 1
                if not any(
                    candidate_matches(candidate, support_raw, support_norm, support_compact)
                    for candidate in candidates
                ):
                    errors.append(
                        f"{chapter_label}: missing must_cover item for {kp_id} "
                        f"detail_cards[{card_index}].must_cover[{item_index}]: "
                        f"{candidates[0]!r} (aliases: {candidates[1:]})"
                    )

    return errors, warnings, checked, deferred


def main(argv: list[str]) -> int:
    if argv:
        chapters = [Path(arg) for arg in argv]
    else:
        chapters = sorted((ROOT / "book").glob("ch*.md"))

    kp_by_id = {str(kp.get("id")): kp for kp in knowledge_points() if kp.get("id")}
    all_errors: list[str] = []
    all_warnings: list[str] = []
    checked_total = 0
    deferred_total = 0

    for chapter in chapters:
        path = chapter if chapter.is_absolute() else ROOT / chapter
        if not path.exists():
            all_errors.append(f"{chapter}: file does not exist")
            continue
        errors, warnings, checked, deferred = check_chapter(path, kp_by_id)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        checked_total += checked
        deferred_total += deferred

    for warning in all_warnings:
        print(f"WARNING: {warning}")
    for error in all_errors:
        print(f"ERROR: {error}")
    if all_errors:
        return 1
    print(
        f"OK: checked {checked_total} must-cover item(s) "
        f"across {len(chapters)} chapter(s) ({deferred_total} deferred)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
