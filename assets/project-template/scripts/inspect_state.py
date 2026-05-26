#!/usr/bin/env python3
"""Inspect project state and propose the next workflow action."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from common import ROOT, knowledge_points, load_yaml, rel, source_index, workflow_state


SOURCE_EXTS = {".ppt", ".pptx", ".pdf"}
SOURCE_DIRS = ["PPTs", "sources/ppts", "sources/ppt", "sources"]

STAGE_FROM_ACTION = {
    "new_chapter": "write_chapter",
    "patch_chapter": "integrate_supplement",
}
STAGE_SHORT_ID = {
    "write_chapter": "write",
    "integrate_supplement": "patch",
}


def derive_job_id(stage: str, target: str) -> str:
    short = STAGE_SHORT_ID.get(stage, stage.replace("_", "-"))
    slug = PurePosixPath(target).stem if target else "unknown"
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{short}-{slug}-{date}"


def discover_source_files() -> list[str]:
    files: set[str] = set()
    for source_dir in SOURCE_DIRS:
        root = ROOT / source_dir
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in SOURCE_EXTS:
                if "extracted" in path.parts:
                    continue
                files.add(rel(path))
    return sorted(files)


def indexed_sources(index: dict[str, Any]) -> set[str]:
    return {
        str(item.get("path"))
        for item in index.get("sources", [])
        if isinstance(item, dict) and item.get("path")
    }


def inspect() -> dict[str, Any]:
    index = source_index()
    kps = knowledge_points()
    state = workflow_state()
    lab_policy = load_yaml("spec/lab-policy.yaml", {"enabled": "missing"})
    quality_overrides = load_yaml("spec/quality-overrides.yaml", {"legacy_chapters": []})

    discovered = discover_source_files()
    indexed = indexed_sources(index)
    unindexed = [path for path in discovered if path not in indexed]

    status_counts = Counter(str(kp.get("status", "missing")) for kp in kps)
    notice_counts = Counter(str(kp.get("reader_notice", "none")) for kp in kps)

    queued_actions: dict[str, list[str]] = defaultdict(list)
    queued_jobs: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    locks: list[dict[str, str]] = []
    for kp in kps:
        kp_id = str(kp.get("id", "<missing-id>"))
        queue = kp.get("queue") or {}
        if kp.get("status") == "queued":
            action = str(queue.get("action", "unspecified"))
            target = str(queue.get("target") or "")
            batch = str(queue.get("batch") or "")
            queued_actions[action].append(kp_id)
            queued_jobs[(action, target, batch)].append(kp_id)
        if kp.get("locked_by"):
            locks.append(
                {
                    "kp": kp_id,
                    "locked_by": str(kp.get("locked_by")),
                    "target": str(kp.get("lock_target", "")),
                }
            )

    chapters = sorted(rel(path) for path in (ROOT / "book").glob("ch*.md"))
    supplements = sorted(rel(path) for path in (ROOT / "book" / "supplements").glob("*.md"))
    legacy_chapters = [
        str(path)
        for path in quality_overrides.get("legacy_chapters", []) or []
        if isinstance(path, str)
    ]

    current_job = state.get("current_job")
    interrupted = bool(current_job or locks)

    actions: list[dict[str, Any]] = []
    if interrupted:
        actions.append(
            {
                "stage": "resume_or_abort",
                "reason": "workflow has an active job or locked knowledge points",
                "requires_user_choice": True,
            }
        )
    if unindexed:
        actions.append(
            {
                "stage": "ingest",
                "reason": f"{len(unindexed)} source file(s) are not in spec/source-index.yaml",
                "files": unindexed,
            }
        )
    if status_counts.get("pool", 0):
        actions.append(
            {
                "stage": "rebalance",
                "reason": f"{status_counts['pool']} knowledge point(s) are in pool",
            }
        )
    if queued_jobs:
        for (action, target, batch), kp_ids in sorted(queued_jobs.items()):
            if action == "hold":
                # hold is a deliberate parking state; no next stage to propose
                continue
            stage = STAGE_FROM_ACTION.get(action)
            if not stage:
                continue
            suggested_job_id = derive_job_id(stage, target)
            next_command = [
                "python3", "scripts/workflow_job.py", "start",
                "--id", suggested_job_id,
                "--stage", stage,
                "--target", target,
                "--batch", batch,
                "--queue-action", action,
                "--kps", *kp_ids,
            ]
            reason_target = target or "<missing target>"
            actions.append(
                {
                    "stage": stage,
                    "reason": f"{len(kp_ids)} queued KP(s) for {action} -> {reason_target}",
                    "kp_ids": kp_ids,
                    "target": target,
                    "batch": batch,
                    "queue_action": action,
                    "suggested_job_id": suggested_job_id,
                    "next_command": next_command,
                }
            )
    pending_supplements = [
        str(kp.get("id", "<missing-id>"))
        for kp in kps
        if kp.get("reader_notice") == "needed"
    ]
    if pending_supplements:
        actions.append(
            {
                "stage": "reader_notice",
                "reason": f"{len(pending_supplements)} KP(s) need reader supplement notices",
                "kp_ids": pending_supplements,
            }
        )

    return {
        "root": str(ROOT),
        "sources": {
            "discovered": discovered,
            "indexed": sorted(indexed),
            "unindexed": unindexed,
            "batches": len(index.get("batches", []) or []),
        },
        "knowledge_points": {
            "total": len(kps),
            "status_counts": dict(status_counts),
            "reader_notice_counts": dict(notice_counts),
            "queued_actions": dict(queued_actions),
            "locks": locks,
        },
        "chapters": chapters,
        "legacy_chapters": legacy_chapters,
        "supplements": supplements,
        "lab_policy": lab_policy.get("enabled", "missing"),
        "workflow": {
            "current_job": current_job,
            "interrupted": interrupted,
        },
        "actions": actions,
        "requires_proposal": len(actions) > 1 or interrupted,
    }


def print_text(report: dict[str, Any]) -> None:
    print(f"Project: {report['root']}")
    print(f"Sources: {len(report['sources']['indexed'])} indexed, {len(report['sources']['unindexed'])} unindexed")
    if report["sources"]["unindexed"]:
        for path in report["sources"]["unindexed"]:
            print(f"  - unindexed: {path}")
    kp = report["knowledge_points"]
    print(f"Knowledge points: {kp['total']} total; statuses={kp['status_counts']}")
    if kp["locks"]:
        print("Locked KP:")
        for lock in kp["locks"]:
            print(f"  - {lock['kp']} locked_by={lock['locked_by']} target={lock['target']}")
    print(f"Chapters: {len(report['chapters'])}; Supplements: {len(report['supplements'])}")
    print(f"Legacy chapters (no visual-plan): {len(report.get('legacy_chapters', []))}")
    print(f"Lab policy: {report['lab_policy']}")
    if report["workflow"]["current_job"]:
        print(f"Current job: {report['workflow']['current_job']}")
    if report["actions"]:
        print("Suggested actions:")
        for action in report["actions"]:
            print(f"  - {action['stage']}: {action['reason']}")
    else:
        print("Suggested actions: none")
    if report["requires_proposal"]:
        print("Routing: propose the next step and wait for approval unless the user explicitly requested one stage.")
    else:
        print("Routing: a single next stage is available.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    report = inspect()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
