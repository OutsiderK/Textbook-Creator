#!/usr/bin/env python3
"""Validate lab structure according to spec/lab-policy.yaml."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from common import ROOT, load_yaml, rel


def truthy(value) -> bool:
    return value is True or str(value).lower() in {"true", "yes", "required"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true", help="Run verify.sh for labs that have one.")
    args = parser.parse_args()

    policy = load_yaml("spec/lab-policy.yaml", {"enabled": "missing"})
    enabled = policy.get("enabled")
    if enabled in {False, "false", "no", "disabled"}:
        print("OK: labs disabled by policy")
        return 0
    if enabled in {"undecided", None, "missing"}:
        print(f"OK: lab policy is {enabled}; no lab validation required yet")
        return 0

    requires_verify = truthy((policy.get("deliverables") or {}).get("verify_script"))
    lab_dirs = [path for path in (ROOT / "labs").iterdir() if path.is_dir()]
    errors: list[str] = []

    for lab_dir in sorted(lab_dirs):
        if not (lab_dir / "README.md").exists():
            errors.append(f"{rel(lab_dir)}: missing README.md")
        verify = lab_dir / "verify.sh"
        if requires_verify and not verify.exists():
            errors.append(f"{rel(lab_dir)}: missing verify.sh")
        if args.run and verify.exists():
            result = subprocess.run(["bash", str(verify)], cwd=lab_dir, text=True)
            if result.returncode != 0:
                errors.append(f"{rel(lab_dir)}: verify.sh failed with {result.returncode}")

    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print(f"OK: checked {len(lab_dirs)} lab(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

