#!/usr/bin/env python3
"""Start, finish, validate, or abort resumable workflow jobs."""

from __future__ import annotations

import argparse
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import ROOT, load_yaml, write_yaml


VALID_HOLD_REASON = {
    "awaiting_followup", "bridging_undefined",
    "enrichment_only", "manual_review",
}

WRITE_CHAPTER_CHECKS = (
    ("check_kp_schema.py", ()),
    ("check_chapter_frontmatter.py", ()),
    ("check_detail_coverage.py", ("{target}",)),
    ("check_visual_assets.py", ("{target}",)),
    ("check_chapter_presentation.py", ("{target}",)),
    ("check_open_questions.py", ()),
)

FINISH_GATE_CHECKS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "write_chapter": WRITE_CHAPTER_CHECKS,
    "integrate_supplement": (
        ("check_kp_schema.py", ()),
        ("check_chapter_frontmatter.py", ()),
        ("check_detail_coverage.py", ("{target}",)),
        ("check_open_questions.py", ()),
    ),
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def visual_plan_path_for_target(target: str) -> str:
    stem = os.path.splitext(os.path.basename(target))[0]
    return f"spec/visual-plans/{stem}.yaml"


def format_check_args(args: tuple[str, ...], target: str) -> list[str]:
    return [arg.replace("{target}", target) for arg in args]


def run_gate_checks(checks: tuple[tuple[str, tuple[str, ...]], ...], target: str) -> tuple[bool, list[str]]:
    """Run each checker as a subprocess; return (all_passed, captured_lines)."""
    scripts_dir = Path(__file__).resolve().parent
    all_ok = True
    output_lines: list[str] = []
    for script, script_args in checks:
        path = scripts_dir / script
        rendered_args = format_check_args(script_args, target)
        suffix = f" {' '.join(rendered_args)}" if rendered_args else ""
        output_lines.append(f"--- {script}{suffix} ---")
        if not path.exists():
            output_lines.append(f"missing checker script: {path}")
            all_ok = False
            continue
        proc = subprocess.run(
            ["python3", str(path), *rendered_args],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        if proc.stdout:
            output_lines.extend(proc.stdout.rstrip("\n").splitlines())
        if proc.stderr:
            output_lines.extend(proc.stderr.rstrip("\n").splitlines())
        if proc.returncode != 0:
            all_ok = False
    return all_ok, output_lines


def print_stage_c_start_checklist(target: str) -> None:
    checklist = Path(__file__).resolve().parent / "_stage_c_checklist.txt"
    print(f"Stage C target: {target}")
    print(f"Visual plan path: {visual_plan_path_for_target(target)}")
    print()
    print("=== STAGE C CHECKLIST (must satisfy before finish) ===")
    if checklist.exists():
        print(checklist.read_text(encoding="utf-8").rstrip())
    else:
        print("MUST read online-course-textbook/references/write-chapter.md before edits.")
        print("MUST create/update the target visual plan before finish.")
    print("=== END ===")


def load_all() -> tuple[dict[str, Any], dict[str, Any]]:
    state = load_yaml("spec/workflow-state.yaml", {"version": 1, "current_job": None, "history": []})
    kp_data = load_yaml("spec/knowledge-points.yaml", {"version": 1, "knowledge_points": []})
    state.setdefault("history", [])
    kp_data.setdefault("knowledge_points", [])
    return state, kp_data


def find_kp(kps: list[dict[str, Any]], kp_id: str) -> dict[str, Any] | None:
    for kp in kps:
        if kp.get("id") == kp_id:
            return kp
    return None


def cmd_start(args: argparse.Namespace) -> int:
    state, kp_data = load_all()
    if state.get("current_job"):
        print(f"ERROR: current_job already exists: {state['current_job'].get('id')}")
        return 1

    if args.queue_action == "hold":
        if args.reason not in VALID_HOLD_REASON:
            print(
                f"ERROR: --queue-action hold requires --reason in "
                f"{sorted(VALID_HOLD_REASON)}, got {args.reason!r}"
            )
            return 1
    elif args.reason is not None:
        print(
            f"ERROR: --reason is only valid with --queue-action hold "
            f"(got --queue-action {args.queue_action!r})"
        )
        return 1

    missing = [kp_id for kp_id in args.kps if find_kp(kp_data["knowledge_points"], kp_id) is None]
    if missing:
        print(f"ERROR: missing KP ids: {', '.join(missing)}")
        return 1

    job = {
        "id": args.id,
        "stage": args.stage,
        "target": args.target,
        "batch": args.batch,
        "kp_ids": args.kps,
        "started_at": now(),
    }
    state["current_job"] = job
    for kp_id in args.kps:
        kp = find_kp(kp_data["knowledge_points"], kp_id)
        if not kp:
            continue
        kp["status"] = "queued"
        kp["locked_by"] = args.id
        kp["lock_stage"] = args.stage
        kp["lock_target"] = args.target
        kp.setdefault("queue", {})
        if args.queue_action:
            kp["queue"]["action"] = args.queue_action
        if args.target:
            kp["queue"]["target"] = args.target
        if args.queue_action == "hold" and args.reason:
            kp["queue"]["reason"] = args.reason

    write_yaml("spec/workflow-state.yaml", state)
    write_yaml("spec/knowledge-points.yaml", kp_data)
    print(f"OK: started job {args.id}")
    if args.stage == "write_chapter":
        print_stage_c_start_checklist(args.target)
    return 0


def cmd_finish(args: argparse.Namespace) -> int:
    state, kp_data = load_all()
    job = state.get("current_job")
    if not job or job.get("id") != args.id:
        print(f"ERROR: current_job is not {args.id!r}")
        return 1

    stage = str(job.get("stage", ""))
    gate_checks = FINISH_GATE_CHECKS.get(stage)
    if gate_checks:
        ok, output = run_gate_checks(gate_checks, args.applied_to)
        for line in output:
            print(line)
        if not ok:
            mode = os.environ.get("STAGE_C_HARD_CHECKS", "enforce").strip().lower()
            if stage == "write_chapter" and mode == "warn":
                print()
                print(
                    "WARNING: finish gate checks failed, but STAGE_C_HARD_CHECKS=warn; "
                    "continuing without blocking."
                )
            else:
                print()
                print(f"ERROR: finish refused for job {args.id!r}: gate checks failed (see output above).")
                print("Fix the reported issues, then re-run the same finish command.")
                return 1

    for kp_id in job.get("kp_ids", []):
        kp = find_kp(kp_data["knowledge_points"], kp_id)
        if not kp:
            continue
        kp["status"] = "applied"
        kp.pop("locked_by", None)
        kp.pop("lock_stage", None)
        kp.pop("lock_target", None)
        kp.pop("queue", None)
        applied = list(kp.get("applied_to") or [])
        if args.applied_to and args.applied_to not in applied:
            applied.append(args.applied_to)
        kp["applied_to"] = applied
        if args.reader_notice:
            kp["reader_notice"] = args.reader_notice
        else:
            kp.setdefault("reader_notice", "none")

    completed = dict(job)
    completed["completed_at"] = now()
    completed["result"] = "completed"
    state.setdefault("history", []).append(completed)
    state["current_job"] = None
    write_yaml("spec/workflow-state.yaml", state)
    write_yaml("spec/knowledge-points.yaml", kp_data)
    print(f"OK: finished job {args.id}")
    return 0


def cmd_abort(args: argparse.Namespace) -> int:
    state, kp_data = load_all()
    job = state.get("current_job")
    if not job or job.get("id") != args.id:
        print(f"ERROR: current_job is not {args.id!r}")
        return 1
    for kp_id in job.get("kp_ids", []):
        kp = find_kp(kp_data["knowledge_points"], kp_id)
        if not kp:
            continue
        kp["status"] = args.to_status
        kp.pop("locked_by", None)
        kp.pop("lock_stage", None)
        kp.pop("lock_target", None)
        if args.to_status == "pool":
            kp.pop("queue", None)

    aborted = dict(job)
    aborted["completed_at"] = now()
    aborted["result"] = "aborted"
    state.setdefault("history", []).append(aborted)
    state["current_job"] = None
    write_yaml("spec/workflow-state.yaml", state)
    write_yaml("spec/knowledge-points.yaml", kp_data)
    print(f"OK: aborted job {args.id}; KP status -> {args.to_status}")
    if job.get("stage") == "write_chapter" and job.get("target"):
        print(f"Visual plan, if present, was kept as draft: {visual_plan_path_for_target(str(job['target']))}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    checks = WRITE_CHAPTER_CHECKS
    ok, output = run_gate_checks(checks, args.target)
    for line in output:
        print(line)
    if not ok:
        print()
        print(f"ERROR: validate failed for {args.target!r}")
        return 1
    print()
    print(f"OK: validate passed for {args.target}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    start = sub.add_parser("start")
    start.add_argument("--id", required=True)
    start.add_argument("--stage", required=True)
    start.add_argument("--target", required=True)
    start.add_argument("--batch", default="manual")
    start.add_argument("--queue-action", choices=["new_chapter", "patch_chapter", "hold"])
    start.add_argument(
        "--reason",
        choices=sorted(VALID_HOLD_REASON),
        help="Required when --queue-action is hold; forbidden otherwise.",
    )
    start.add_argument("--kps", nargs="+", required=True)
    start.set_defaults(func=cmd_start)

    finish = sub.add_parser("finish")
    finish.add_argument("--id", required=True)
    finish.add_argument("--applied-to", required=True)
    finish.add_argument("--reader-notice", choices=["none", "needed", "published"])
    finish.set_defaults(func=cmd_finish)

    abort = sub.add_parser("abort")
    abort.add_argument("--id", required=True)
    abort.add_argument("--to-status", choices=["pool", "queued"], default="queued")
    abort.set_defaults(func=cmd_abort)

    validate = sub.add_parser("validate")
    validate.add_argument("target")
    validate.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
