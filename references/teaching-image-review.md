# Reference: Stage A — Teaching-image prepass

Read this reference together with `references/ingest.md` during Stage A. The project-local scripts are the deterministic harness; this document controls the agent review that follows it.

## Purpose

Identify slide pages containing instructional images while filtering template and decorative imagery. Optimize for recall: never drop a plausible teaching-image page unless visual review confirms that it is non-instructional.

This prepass finds embedded-image evidence. It does not replace the comprehension-blocker checks in `ingest.md`; pages with tables, formulas, code, diagrams, or broken text order may still require visual review even when the scanner reports `no_images`.

## Required workflow

1. Run the project-local scanner before formal KP extraction:

   ```bash
   python3 scripts/scan_teaching_image_pages.py \
     sources/ppts/<file>.pdf \
     --out tmp/page-review/batch-<batch>/teaching-image-scan
   ```

2. Use `teaching_image_pages.json` as the structural scan record. Review `contact_high_recall_*.jpg` first; also inspect `contact_review_*.jpg` and, when useful, `contact_template_audit_*.jpg`. Escalate ambiguous pages to the rendered full page.
3. Fill every row of `review_decisions_template.csv` with `confirmed`, `uncertain`, or `excluded`. Every excluded page needs a short evidence-based reason.
4. Run the project-local finalizer:

   ```bash
   python3 scripts/finalize_review_decisions.py \
     tmp/page-review/batch-<batch>/teaching-image-scan/teaching_image_pages.json \
     tmp/page-review/batch-<batch>/teaching-image-scan/review_decisions_template.csv
   ```

   A nonzero exit is a hard Stage A blocker. Fix the ledger instead of bypassing the finalizer.
5. Treat `confirmed + uncertain` from the validated ledger as the teaching-image contribution to `final_visual_review_pages`. Render every retained page and create its `visual_page_notes` before extracting KPs.

## Review policy

Count a page as containing a teaching image when the visual object is part of the lesson content:

- Photos, screenshots, scans, maps, scientific images, historical artifacts, UI/code/document screenshots.
- Diagrams, figures, plots, charts, architecture drawings, timelines, workflows, equations rendered as images, or visual examples explained by the slide.
- Repeated course-content figures in the slide body, including build-up sequences across adjacent slides.
- Small images when they are the object being taught, such as icon sets in a UI lecture.

Exclude only when the visual is confidently non-instructional:

- Logos, slide numbers, watermarks, repeated header/footer strips or sidebars.
- Background texture, theme imagery, repeated title-template art, or decorative dividers.
- Tiny bullet icons, ornaments, brand marks, or navigation marks.
- Administrative portraits or QR codes that are not part of the taught content.

When uncertain, keep the page and mark it `uncertain`. Repetition alone is not enough to exclude a body-area image.

Inspect a full-page render when a candidate is small but central, when the template audit contains a large body-area visual, or when adjacent slide builds may hide or reveal parts of the same figure. If repeated backgrounds cause nearly every page to be promoted, still complete the same ledger workflow; do not hand-prune the candidate set.

## Harness invariants

- `high_recall_pages = likely_pages + review_pages` is the review universe.
- The decision ledger must cover every page in `high_recall_pages`; blank or duplicate decisions are blockers.
- Excluded pages require reasons.
- Final teaching-image pages come from the finalizer, never from a manually retyped list.
- Do not load all PDF pages into context. Use contact sheets first and full-page renders only where needed.
- Do not ask the model to inspect pages classified as `no_images` unless the text skeleton or neighboring context makes them comprehension blockers.
- Before finishing Stage A, reconcile the validated ledger with `teaching_image_scan.confirmed` and `.uncertain` in the page-risk audit, and ensure every retained page has a matching `final_visual_review_pages` and `visual_page_notes` entry.

## Scanner model

The scanner exhaustively collects image placement, displayed area, intrinsic size, asset digest, repeated-page count, and repeated same-position count. It marks template imagery only when repetition and decoration signals agree, then scores remaining images conservatively. Weak unique signals go to `review`, not directly to exclusion.

The scanner is a candidate generator, not a semantic judge. The agent review and the finalizer's completeness checks are mandatory parts of the harness.
