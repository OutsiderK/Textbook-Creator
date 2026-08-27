# Reference: Quality Checks

Map of scripts to severity and when to run them. All scripts assume the current working directory is the project root.

## Severity Model

| Severity | Meaning |
|---|---|
| hard | Failure stops the stage. For Stage C/D, do not `workflow_job.py finish`; fix first. |
| soft | Warning only. Report it, but it does not block finish. |

## Script Map

| Script | When | Severity | Validates |
|---|---|---|---|
| `inspect_state.py` | Every invocation and after every stage | state report | Project state and next actions |
| `check_kp_schema.py` | After A/B/C/D | hard | KP schema, status/queue rules, card fields |
| `finalize_review_decisions.py` | During A, before KP extraction | hard | Every high-recall page has a valid decision and every exclusion has evidence |
| `check_page_risk.py docs/page-risk-<batch>.yaml` | After A | hard | Stage A page-risk audit; supports legacy v1 contact-sheet audits and v2 visual_page_notes audits |
| `check_chapter_frontmatter.py` | After C/D | hard | Chapter front matter and forbidden workflow terms |
| `check_detail_coverage.py` | After C/D | hard | `must_cover` appears in chapter/support text unless deferred |
| `check_visual_assets.py` | After C | hard | Visual plan exists; declared outputs match chapter/assets; structural carriers cover `must_cover` |
| `check_chapter_presentation.py` | After C | hard + soft | Formula variable tables, `exam_tip` consumption, and scan-structure warnings |
| `check_open_questions.py` | After B/C/D | soft | Open-question structure and cross references |
| `check_lab.py` | After lab module | hard for code labs; soft for observation labs | Lab files and verification |

## Stage C Preferred Entry

Use the workflow wrapper:

```bash
python3 scripts/workflow_job.py validate book/chNN-slug.md
```

`validate` does not require an active job. It runs the same Stage C check path as `finish` and returns 1 on hard failure. Soft warnings return 0.

## After Init

```bash
python3 scripts/check_kp_schema.py
python3 scripts/inspect_state.py --json
```

## After Stage A (Ingest)

```bash
python3 scripts/finalize_review_decisions.py \
  tmp/page-review/batch-<batch>/teaching-image-scan/teaching_image_pages.json \
  tmp/page-review/batch-<batch>/teaching-image-scan/review_decisions_template.csv
python3 scripts/check_kp_schema.py
python3 scripts/check_page_risk.py docs/page-risk-<batch>.yaml
```

Visual audit fields on `detail_cards` are expected: `visual_reviewed`, `review_risk_level`, `page_class`, `structure_kind`, `verified_items`, and `must_cover[].item/aliases/role/deferred/defer_reason`.
For legacy schema v1, page-risk audits must include `thumbnail_scan` for every page and classification review evidence for every `visual_candidate: true` page. For schema v2, `page_risks` must cover every page, teaching-image `confirmed + uncertain` pages and comprehension blockers must appear in `final_visual_review_pages`, and every final visual-review page must have a matching `visual_page_notes` entry with non-empty `must_capture`.

## After Stage B (Rebalance)

```bash
python3 scripts/check_kp_schema.py
python3 scripts/check_open_questions.py
```

## After Stage C (Write Chapter)

Before finish:

```bash
python3 scripts/workflow_job.py validate book/chNN-slug.md
```

Equivalent direct checks:

```bash
python3 scripts/check_kp_schema.py
python3 scripts/check_chapter_frontmatter.py
python3 scripts/check_detail_coverage.py book/chNN-slug.md
python3 scripts/check_visual_assets.py book/chNN-slug.md
python3 scripts/check_chapter_presentation.py book/chNN-slug.md
python3 scripts/check_open_questions.py
```

Hard failures include:

- Missing or invalid front matter.
- Detail `must_cover` missing from support text.
- Missing `spec/visual-plans/<stem>.yaml`.
- Required card missing from visual plan.
- `card_ref` matches zero or multiple cards.
- Declared SVG/table/formula/steps/callout/prose output not found.
- `representation: [prose]` without a non-empty `reason`.
- Formula block without an adjacent variable table.
- `exam_tip` not consumed through `==...==`, callout, or exercise/answer.

Soft warnings include:

- No figure/table in a chapter with no relevant visual card.
- Many long plain paragraphs.
- Many callouts.
- No recognized callout.

`spec/quality-overrides.yaml` may list legacy chapters that pre-date visual plans. The new Stage C checks skip those chapters with a warning and `inspect_state.py` reports the debt count.

## After Stage D (Integrate Supplement)

```bash
python3 scripts/check_kp_schema.py
python3 scripts/check_chapter_frontmatter.py
python3 scripts/check_detail_coverage.py book/chMM-slug.md
python3 scripts/check_open_questions.py
```

After hard checks pass, run `workflow_job.py finish ... --reader-notice published`, then `inspect_state.py --json`.

## After Lab Module

```bash
python3 scripts/check_lab.py labs/labXX-slug/
```

## All Clean State

If `inspect_state.py` returns `actions: []` and no active job:

```bash
python3 scripts/check_kp_schema.py
python3 scripts/check_open_questions.py
python3 scripts/check_chapter_frontmatter.py
python3 scripts/check_detail_coverage.py
python3 scripts/check_visual_assets.py
python3 scripts/check_chapter_presentation.py
python3 scripts/check_lab.py
```

## Report Format

Use a compact summary:

```text
✓ check_kp_schema  (89 KPs, 0 errors)
✗ check_visual_assets book/ch08-memory-management.md
    - missing visual plan spec/visual-plans/ch08-memory-management.yaml
⚠ check_chapter_presentation
    - no recognized callout found
```

Hard failures must be fixed before stage completion. Do not let check scripts silently repair semantic content.
