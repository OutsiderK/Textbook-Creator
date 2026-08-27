#!/usr/bin/env python3
"""End-to-end regression tests for the Stage A teaching-image harness."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

import fitz
from PIL import Image


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "assets" / "project-template" / "scripts"
SCANNER = SCRIPTS / "scan_teaching_image_pages.py"
FINALIZER = SCRIPTS / "finalize_review_decisions.py"
RELEASE_BUILDER = SKILL_ROOT / "scripts" / "build_release.py"


def png_bytes(path: Path, color: tuple[int, int, int]) -> bytes:
    Image.new("RGB", (160, 160), color).save(path)
    return path.read_bytes()


class TeachingImageHarnessTest(unittest.TestCase):
    def make_fixture_pdf(self, root: Path) -> Path:
        unique = png_bytes(root / "unique.png", (220, 40, 40))
        repeated = png_bytes(root / "repeated.png", (40, 80, 220))
        repeated_body = png_bytes(root / "repeated-body.png", (40, 180, 80))
        pdf = root / "fixture.pdf"
        doc = fitz.open()

        page = doc.new_page(width=600, height=450)
        page.insert_text((72, 72), "Text-only control page")

        page = doc.new_page(width=600, height=450)
        page.insert_image(fitz.Rect(120, 90, 480, 390), stream=unique)

        for _ in range(5):
            page = doc.new_page(width=600, height=450)
            page.insert_image(fitz.Rect(8, 8, 38, 38), stream=repeated)

        # A repeated body-area teaching figure must not be discarded merely
        # because it appears in the same place across a slide build sequence.
        for _ in range(4):
            page = doc.new_page(width=600, height=450)
            page.insert_image(fitz.Rect(180, 120, 420, 330), stream=repeated_body)

        doc.save(pdf)
        doc.close()
        return pdf

    def test_scan_and_validated_ledger_preserve_no_miss_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf = self.make_fixture_pdf(root)
            out = root / "scan"

            scan_run = subprocess.run(
                [sys.executable, str(SCANNER), str(pdf), "--out", str(out)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(scan_run.returncode, 0, scan_run.stderr or scan_run.stdout)

            report = json.loads((out / "teaching_image_pages.json").read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["high_recall_pages"], [2, 8, 9, 10, 11])
            self.assertEqual(report["summary"]["likely_pages"], [2, 8, 9, 10, 11])
            self.assertEqual(report["summary"]["no_image_pages"], [1])
            self.assertEqual(report["summary"]["template_only_pages"], [3, 4, 5, 6, 7])
            self.assertTrue(report["summary"]["contact_sheets"]["high_recall"])

            ledger = out / "review_decisions_template.csv"
            blank_run = subprocess.run(
                [sys.executable, str(FINALIZER), str(out / "teaching_image_pages.json"), str(ledger)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(blank_run.returncode, 0)
            self.assertIn("blank decision for page 2", blank_run.stdout)

            with ledger.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
                fields = list(rows[0])
            for row in rows:
                row["decision"] = "uncertain"
                row["reason"] = "kept conservatively for no-miss review"
            with ledger.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)

            final_run = subprocess.run(
                [sys.executable, str(FINALIZER), str(out / "teaching_image_pages.json"), str(ledger)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(final_run.returncode, 0, final_run.stderr or final_run.stdout)
            self.assertIn("Uncertain / kept for no-miss recall: 2, 8, 9, 10, 11", final_run.stdout)

    def test_release_is_reproducible_and_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.zip"
            second = root / "second.zip"
            for output in (first, second):
                run = subprocess.run(
                    [sys.executable, str(RELEASE_BUILDER), str(output)],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(run.returncode, 0, run.stderr or run.stdout)

            self.assertEqual(first.read_bytes(), second.read_bytes())
            with ZipFile(first) as archive:
                self.assertIsNone(archive.testzip())
                names = set(archive.namelist())
                self.assertIn(
                    "online-course-textbook/assets/project-template/scripts/scan_teaching_image_pages.py",
                    names,
                )
                self.assertIn(
                    "online-course-textbook/references/teaching-image-review.md",
                    names,
                )


if __name__ == "__main__":
    unittest.main()
