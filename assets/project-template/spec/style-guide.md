# Style Guide

## Reader Contract

- The textbook should read like a coherent, polished book, even while the workflow is online and incremental.
- The main chapter file is always the current best version. Supplement files are reader notices for people who already read an earlier version.
- Do not expose workflow words in reader-facing chapter prose or supplements.

### Forbidden tokens (hard fail in checks)

These tokens must NOT appear in `book/**/*.md`:

- `defer`, `future-unknown`, `future_unknown`
- `TODO`, `FIXME`, `XXX`
- `待补充`, `待完善`, `待定`
- `新增`, `本次新增`, `本次补充`, `本次更新`
- `v1`, `v2`, `v1.0`, version markers like `2026-`, `2025-` in chapter prose
- `(将在第 X 章中讲解)` if X is not yet a real chapter id

The check script `check_chapter_frontmatter.py` scans for these.

### Natural boundary language (preferred)

When a chapter cannot cover something deeply yet, say it as part of the narrative:

- "我们这里先把 X 理解为 Y；至于 X 在并发场景下的更完整含义，等学了同步原语之后回头看会更自然些。"
- "本章只关注 A 视角的 B；C 视角的同样问题会在引入 D 工具后变得清晰。"
- "完整的算法分析需要 E 概念支撑，我们先用一个直观的例子建立感觉。"

The signal: the boundary is described as something the **reader** experiences, not something the **author** owes.

## Learning Design

The textbook structure encodes specific cognitive-science principles. Don't drop them just because a chapter feels thin.

| Section | Principle |
|---|---|
| 上章回顾 | Prior-knowledge activation; spaced retrieval |
| 开篇问题 | Anchored instruction / motivating hook |
| 本章地图 | Metacognitive signposting |
| 正文 (痛点→机制→例子→边界) | Worked-example pattern; manage cognitive load |
| 思维停顿 (1-2/章) | Metacognitive prompt; near-transfer recall |
| 例题讲解 | Worked example (Sweller); shows steps not just answer |
| 常见误区 | Misconception preemption |
| 关键术语 中英双语 | Bilingual reinforcement; helps switch between courseware and English literature |
| 练习与解答 (with retrieval_hooks.bridging) | Retrieval practice; near + far transfer |

## Chapter Writing

- Start from a concrete problem, surprising behavior, or motivating question. **Do NOT open with a definition.**
- Prefer the pattern: pain point → idea → mechanism → example → cost or boundary.
- Keep important PPT details (`detail_cards`) when they support exams or understanding: methods, tricks, operation steps, examples, diagrams, formulas, common pitfalls. Cards not used must be explicitly marked `deferred: true`.
- Preserve mature book feel: no dated update boxes, no "newly added" markers.

### Emphasis levels

Use sparingly; consistent meaning:

| Mark | Meaning |
|---|---|
| `**加粗**` | Concept introduction or key claim |
| `*斜体*` | Technical term in flow, secondary emphasis |
| `==高亮==` | Exam point worth memorizing (from `detail_cards.type=exam_tip`) |
| `> 引用` | Sidebar, definition box, or 思维停顿 |
| `` `代码` `` | Identifiers, file names, shell commands |

### Diagram triggers (SVG)

Generate an SVG figure when ANY of these is true (and there's a `detail_cards.type=figure` for it):

- The reader must track 3+ simultaneous states or fields
- Sequential timing or async ordering matters (use a timing diagram)
- Hierarchy or addressing levels (3+ levels) — use a tree/box diagram
- A table would have 5+ rows × 3+ columns of structured relations — consider visualizing
- The original PPT clearly relies on a figure that prose alone won't reproduce

File naming: `assets/figures/chNN-<concept>.svg`. Embed via standard Markdown image syntax.

If the figure is decorative or trivial, prose is fine.

## Rebalance Principles

- PPT order is a weak prior, not a chapter boundary.
- Chapter boundaries should primarily follow knowledge coherence: shared problem, shared mechanism, prerequisites, examples, narrative flow.
- Quantitative KP thresholds are guardrails: 5-9 core KP is usually comfortable; more than 9 requires split review; fewer than 5 requires merge or wait review.
- Heavy mechanisms or algorithms may justify a chapter even with few KP.
- See `references/rebalance.md` "Seven Questions" for the full decision frame.

## Supplement Style

Supplements are not "release notes." They read like depth materials that were always there:

- Title uses the knowledge-point name, not "update X" or a version label.
- No dates, no version numbers, no "本次更新".
- The "建议已读者" section gives a concrete re-read path: "只需补读 X.Y.Z 节，并回看「<相关小节>」末段"。

## Lab Principles

- Lab design is controlled by `spec/lab-policy.yaml`.
- Lab questions and environments must be selected for the course subject, not copied from a generic checklist.
- If labs are enabled, a lab should clarify or test a core mechanism, not sit as an unrelated appendix.
- Runnable labs need starter, reference solution, tests or verification, and clear expected observations.
- TODO mapping by `preferences.course_focus`:
  - `mechanism_understanding` → KP with `role: mechanism`
  - `exam_drill` → KP with `detail_cards.type: exam_tip` or `role: exam_pattern`
  - `engineering_practice` → KP with `detail_cards.type: operation`
