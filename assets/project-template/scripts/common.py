#!/usr/bin/env python3
"""Shared helpers for the online textbook workflow scripts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_yaml(relative: str, default: Any) -> Any:
    path = ROOT / relative
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return default
    data = yaml.safe_load(text)
    return default if data is None else data


def write_yaml(relative: str, data: Any) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000),
        encoding="utf-8",
    )


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def knowledge_points() -> list[dict[str, Any]]:
    data = load_yaml("spec/knowledge-points.yaml", {"knowledge_points": []})
    return list(data.get("knowledge_points") or [])


def source_index() -> dict[str, Any]:
    return load_yaml("spec/source-index.yaml", {"sources": [], "batches": []})


def workflow_state() -> dict[str, Any]:
    return load_yaml("spec/workflow-state.yaml", {"current_job": None, "history": []})

