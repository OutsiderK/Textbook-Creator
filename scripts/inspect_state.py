#!/usr/bin/env python3
"""Inspect project state and report the suggested next action.

Usage:
    python3 inspect_state.py <project-root> [--json]

Without --json, prints a human-readable report.
With --json, prints a JSON dictionary on stdout for programmatic consumption.

This script is the entry point that SKILL.md uses to decide stage routing.
It NEVER modifies the project; pure read-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(2)


PPT_EXTENSIONS = {".pdf", ".pptx", ".ppt"}


def safe_load_yaml(path: Path):
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        return {"_parse_error": str(e)}


def collect_pending_ppts(project_root: Path, source_index):
    inputs_dir = project_root / "inputs"
    if not inputs_dir.exists():
        return []

    seen = set()
    if source_index and isinstance(source_index.get("sources"), list):
        for entry in source_index["sources"]:
            if isinstance(entry, dict) and "file" in entry:
                seen.add(entry["file"])

    pending = []
    for child in sorted(inputs_dir.iterdir()):
        if child.is_file() and child.suffix.lower() in PPT_EXTENSIONS:
            if child.name not in seen:
                pending.append(str(child.relative_to(project_root)))
    return pending


def classify_kp_status(kps):
    """Partition KPs by status into pool / queued_new / queued_patch / applied."""
    by = {
        "pool": [],
        "queued_new": [],
        "queued_patch": [],
        "applied": [],
        "unknown": [],
    }
    for kp in kps:
        if not isinstance(kp, dict):
            continue
        kp_id = kp.get("id", "<no-id>")
        status = kp.get("status")
        if status == "pool":
            by["pool"].append(kp_id)
        elif status == "queued":
            action = kp.get("action")
            reader_notice = kp.get("reader_notice", "none")
            if action == "patch_chapter" or reader_notice == "needed":
                by["queued_patch"].append(kp_id)
            else:
                by["queued_new"].append(kp_id)
        elif status == "applied":
            by["applied"].append(kp_id)
        else:
            by["unknown"].append(kp_id)
    return by


def chapters_ready_for_write(kps_queued_new):
    """Group queued_new KP ids by their applied_to chapter."""
    return None  # placeholder, computed in main with full KP dicts


def suggest_next_action(state):
    """Apply the priority-ordered router from SKILL.md."""
    if state["in_progress"]:
        return "resume_or_discard"
    if not state["initialized"]:
        return "initialize"
    if state["pending_ppts"]:
        return "ingest"
    if state["kp_status"]["pool"]:
        return "rebalance"
    if state["kp_status"]["queued_new"]:
        return "write_chapter"
    if state["kp_status"]["queued_patch"]:
        return "patch_chapter"
    if state.get("lab_pending"):
        return "lab"
    return "check_state"


def collect_state(project_root: Path):
    state = {
        "project_root": str(project_root),
        "initialized": False,
        "in_progress": None,
        "pending_ppts": [],
        "kp_status": {
            "pool": [],
            "queued_new": [],
            "queued_patch": [],
            "applied": [],
            "unknown": [],
        },
        "queued_new_by_chapter": {},
        "queued_patch_by_chapter": {},
        "pending_supplements": [],
        "open_questions_open": 0,
        "lab_policy": None,
        "lab_pending": False,
        "warnings": [],
    }

    spec_dir = project_root / "spec"
    if not spec_dir.exists():
        state["suggested_next_action"] = suggest_next_action(state)
        return state

    # Initialization check: knowledge-points.yaml exists
    kp_path = spec_dir / "knowledge-points.yaml"
    state["initialized"] = kp_path.exists()

    # In-progress lock
    in_progress_path = spec_dir / ".in-progress.yaml"
    if in_progress_path.exists():
        loaded = safe_load_yaml(in_progress_path)
        if isinstance(loaded, dict):
            state["in_progress"] = loaded
        else:
            state["in_progress"] = {"_error": "in-progress file unparseable"}

    # Pending PPTs (vs source-index)
    source_index = safe_load_yaml(spec_dir / "source-index.yaml")
    state["pending_ppts"] = collect_pending_ppts(project_root, source_index)

    # KP status
    if state["initialized"]:
        kp_data = safe_load_yaml(kp_path) or {}
        if isinstance(kp_data, dict) and "_parse_error" in kp_data:
            state["warnings"].append(f"knowledge-points.yaml parse error: {kp_data['_parse_error']}")
            kps = []
        elif isinstance(kp_data, dict):
            kps = kp_data.get("knowledge_points", []) or []
        elif isinstance(kp_data, list):
            kps = kp_data
        else:
            kps = []
        state["kp_status"] = classify_kp_status(kps)

        # Group queued KPs by chapter (full KP dicts available here)
        for kp in kps:
            if not isinstance(kp, dict):
                continue
            if kp.get("status") != "queued":
                continue
            chapter = kp.get("applied_to") or "<unassigned>"
            action = kp.get("action")
            reader_notice = kp.get("reader_notice", "none")
            target = state["queued_patch_by_chapter"] if (
                action == "patch_chapter" or reader_notice == "needed"
            ) else state["queued_new_by_chapter"]
            target.setdefault(chapter, []).append(kp.get("id", "<no-id>"))

            if reader_notice == "needed":
                state["pending_supplements"].append(kp.get("id", "<no-id>"))

    # Open questions count (rough)
    oq_path = spec_dir / "open-questions.md"
    if oq_path.exists():
        text = oq_path.read_text(encoding="utf-8")
        # naive count: lines starting with "## OQ-"
        state["open_questions_open"] = sum(
            1 for line in text.splitlines()
            if line.strip().startswith("## OQ-")
            and "已解决" not in text.split(line)[0].rsplit("\n## ", 1)[0]
        )

    # Lab policy
    lab_policy_path = spec_dir / "lab-policy.yaml"
    if lab_policy_path.exists():
        state["lab_policy"] = safe_load_yaml(lab_policy_path)
        # Lab pending heuristic: policy enabled AND there's a chapter with no lab dir
        if isinstance(state["lab_policy"], dict) and state["lab_policy"].get("enabled") is True:
            # detection of "needs lab" is done by Stage B; here we just expose policy
            state["lab_pending"] = False  # only fires if Stage B marks; not auto

    state["suggested_next_action"] = suggest_next_action(state)
    return state


def render_human(state):
    lines = []
    lines.append(f"# Project state report")
    lines.append(f"Path: {state['project_root']}")
    lines.append(f"Initialized: {state['initialized']}")

    if state["in_progress"]:
        lines.append("")
        lines.append("⚠ IN-PROGRESS LOCK DETECTED")
        ip = state["in_progress"]
        if isinstance(ip, dict):
            for k in ("stage", "batch", "target", "notes"):
                if k in ip:
                    lines.append(f"  {k}: {ip[k]}")
            if "kp_ids" in ip and isinstance(ip["kp_ids"], list):
                lines.append(f"  kp_ids: {len(ip['kp_ids'])} locked")
        lines.append("  → Resume or discard before any other action.")

    if state["pending_ppts"]:
        lines.append("")
        lines.append(f"Pending PPTs ({len(state['pending_ppts'])}):")
        for p in state["pending_ppts"]:
            lines.append(f"  - {p}")

    if state["initialized"]:
        s = state["kp_status"]
        lines.append("")
        lines.append("KP status:")
        lines.append(f"  pool         : {len(s['pool'])}")
        lines.append(f"  queued_new   : {len(s['queued_new'])}")
        lines.append(f"  queued_patch : {len(s['queued_patch'])}")
        lines.append(f"  applied      : {len(s['applied'])}")
        if s["unknown"]:
            lines.append(f"  unknown      : {len(s['unknown'])} (check schema!)")

        if state["queued_new_by_chapter"]:
            lines.append("")
            lines.append("Queued for new chapters:")
            for ch, ids in state["queued_new_by_chapter"].items():
                lines.append(f"  {ch}: {len(ids)} KP")

        if state["queued_patch_by_chapter"]:
            lines.append("")
            lines.append("Queued for chapter patches:")
            for ch, ids in state["queued_patch_by_chapter"].items():
                lines.append(f"  {ch}: {len(ids)} KP (supplement needed)")

    if state["lab_policy"]:
        lp = state["lab_policy"]
        if isinstance(lp, dict):
            lines.append("")
            lines.append(f"Lab policy: enabled={lp.get('enabled', 'unset')}")

    if state["warnings"]:
        lines.append("")
        lines.append("Warnings:")
        for w in state["warnings"]:
            lines.append(f"  - {w}")

    lines.append("")
    lines.append(f"Suggested next action: {state['suggested_next_action']}")

    # short hint per action
    hints = {
        "initialize": "→ Load references/initialize.md",
        "resume_or_discard": "→ Prompt user: resume / discard / cancel",
        "ingest": "→ Load references/ingest.md (target the first pending PPT)",
        "rebalance": "→ Load references/rebalance.md",
        "write_chapter": "→ Load references/write-chapter.md (pick a chapter from queued_new_by_chapter)",
        "patch_chapter": "→ Load references/patch-chapter.md (pick a chapter from queued_patch_by_chapter)",
        "lab": "→ Load references/lab-policy-and-design.md",
        "check_state": "→ Load references/quality-checks.md and run full check pass",
    }
    if state["suggested_next_action"] in hints:
        lines.append(hints[state["suggested_next_action"]])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument("project_root", help="Textbook project directory")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    if not project_root.exists():
        print(f"ERROR: project root does not exist: {project_root}", file=sys.stderr)
        sys.exit(2)

    state = collect_state(project_root)

    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    else:
        print(render_human(state))


if __name__ == "__main__":
    main()
