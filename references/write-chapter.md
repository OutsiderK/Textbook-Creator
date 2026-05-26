# Reference: Stage C - Write Chapter

Trigger: `inspect_state.py --json` reports queued KPs with `queue.action: new_chapter` and a target chapter is ready, or the user explicitly says "写第 N 章 / 生成 chXX".

> **Stage C 的座右铭：成书。** 写出的章节要像一本已经打磨完成的教材：自然、连贯、可扫读、有结构图表，不出现工作流术语。

## Input

- `spec/knowledge-points.yaml` - target queued KPs and their `detail_cards`
- `spec/chapter-template.md`
- `spec/style-guide.md`
- `spec/reference-chapter.md`
- `docs/reference-chapter-annotation.md` when you need to understand the exemplar
- `spec/terminology.md`
- `spec/course-skeleton.md`
- Previous chapter front matter, if present

## Output

- `book/chNN-slug.md` - reader-facing chapter
- `assets/figures/chNN-*.svg` - chapter figures, when the visual plan declares SVG output
- `spec/visual-plans/<stem>.yaml` - auditable presentation contract
- `spec/course-skeleton.md` - target chapter status updated to `drafted`
- `spec/open-questions.md` - closed or newly registered OQs
- KP status flips only through `workflow_job.py finish`

`<stem>` is derived exactly as:

```python
os.path.splitext(os.path.basename(target))[0]
```

For target `book/ch03-kernel-boundary-and-structure.md`, the visual plan path is `spec/visual-plans/ch03-kernel-boundary-and-structure.yaml`. All scripts and docs use this derivation.

**Do NOT touch**: source-index, terminology, style-guide, chapter-template, unrelated chapters, or supplements.

## Start the Job

Before edits, lock the target KPs:

```bash
python3 scripts/workflow_job.py start \
  --id write-ch08-memory-management-20260526 \
  --stage write_chapter \
  --target book/ch08-memory-management.md \
  --batch 003 \
  --queue-action new_chapter \
  --kps OSPPT-CH08-PAGE-TABLE OSPPT-CH08-TLB
```

If a job is active, resume or abort it before starting another job.

### Abort Semantics

`workflow_job.py abort` does not delete the visual plan. If a plan exists, keep `status: draft`. On the next `start` for the same target, read the existing draft and decide whether to revise it or overwrite it.

## Stage C Internal Order

Do not split these into separate workflow jobs. They are the internal order of one `write_chapter` job.

### C.0 Visual and Presentation Plan

1. Read target KPs and all `detail_cards`.
2. Create or update `spec/visual-plans/<stem>.yaml`.
3. Every non-deferred card with `visual_reviewed: true`, `type: figure`, or non-empty `must_cover` must appear in the visual plan.
4. For each planned card or group, decide representation: `svg`, `table`, `formula`, `steps`, `callout`, `prose`, or a list such as `[formula, steps, callout]`.
5. Multiple cards may be grouped only when grouping improves reader understanding; grouped items require `reason`.
6. `prose` is allowed only with a non-empty `reason`.
7. Start with `status: draft`.

### C.1 Prose Draft

Write natural textbook prose. Natural prose does not mean pure text:

- Paragraphs explain causes, tradeoffs, and narrative flow.
- Figures preserve structure.
- Tables preserve comparison and classification.
- Formula blocks preserve quantitative relations.
- Steps preserve order.
- Callouts preserve key judgments and exam distinctions.

### C.2 Structured Components

Generate or revise the declared SVG/table/formula/steps/callout outputs. If the plan decision proves wrong while writing, revise the visual plan in place, then revise the chapter or asset. Do not force a bad figure just because the draft plan said `svg`.

### C.3 Presentation Self-check

Set the visual plan to `status: final` only after it matches the final chapter and assets. Run the self-check questions below before finish.

### C.4 Finish

Run checks or `workflow_job.py validate <target>`. Only call `workflow_job.py finish` after hard checks pass.

## Visual Plan Schema

Use `card_ref`, not array indexes.

```yaml
version: 1
chapter: ch03-kernel-boundary-and-structure
target: book/ch03-kernel-boundary-and-structure.md
status: draft

items:
  - id: vp-ch03-001
    kp: OSPPT-CH01-BOOT-AND-INIT
    card_ref:
      source_slide: 18
      card_type: figure
    visual_reviewed: true
    page_class: process_diagram
    structure_kind: ordered_chain
    must_cover:
      - BIOS / bootblocks
      - Master Boot Record
      - LILO / GRUB
      - Linux
      - User space
    representation: [svg]
    output:
      svg: assets/figures/ch03-boot-chain.svg
    placement:
      markdown_after_heading: "3.1 从上电到用户空间"
    reason: 引导链是控制转移顺序，流程图比纯散文更能保留结构。

  - id: vp-ch03-002
    group:
      - kp: OSPPT-CH01-SYSCALL-LAYERING-PROCESS
        card_ref:
          source_slide: 52
          card_type: figure
      - kp: OSPPT-CH01-SYSCALL-LAYERING-PROCESS
        card_ref:
          source_slide: 53
          card_type: figure
    representation: [svg, callout]
    output:
      svg: assets/figures/ch03-syscall-boundary-callchain.svg
      callout: "系统调用不是普通函数调用，因为它跨越用户态/核心态边界。"
    reason: 两张图共同表达边界和调用链，合并能减少重复。

  - id: vp-ch03-999
    kp: EXAMPLE-KP
    card_ref:
      source_slide: 99
      card_type: method
    representation: [prose]
    output:
      prose: "这条方法只作为正文中的一句约束出现。"
    reason: 该卡片只是普通术语提醒，没有独立结构。
```

Within the same KP, `(source_slide, card_type)` should identify exactly one detail card. If a checker reports zero or multiple matches, refine the card metadata before finish.

## Structure Mapping

Use this default mapping unless the chapter context gives a better reason.

| `structure_kind` / `page_class` | Default representation |
|---|---|
| `ordered_chain` | SVG flow, step diagram, or ordered steps |
| `comparison` | Comparison table or two-column diagram |
| `state_machine` | State diagram or state-event-transition table |
| `formula` | Formula block + variable table + small example |
| `architecture_diagram` | Layer/component diagram |
| `table` / `comparison_table` | Markdown table; SVG only for complex layout |
| `case_steps` | Steps table, timeline, or flow diagram |
| `code_or_command` | Code block + call-chain explanation |
| `chart_or_plot` | Simplified figure, data table, or conclusion callout |
| `taxonomy` | Classification table or tree diagram |

## Representation Checks

All representation checks use a declared-output pattern. The visual plan declares exact text or paths; check scripts match substrings or file existence. They do not judge beauty or deep semantics.

| representation | `output` field | Check method |
|---|---|---|
| `svg` | `output.svg: <path>` | File exists, chapter contains `![...](path)`, SVG `<text>` covers `must_cover` |
| `table` | `output.table.headers: [...]` | A Markdown table exists; each header substring appears; table cells cover `must_cover` |
| `formula` | `output.formula: "$$..LaTeX..$$"` | Chapter contains a `$$...$$` block with that exact substring; the formula block is adjacent to a variable table |
| `steps` | `output.steps: ["step1", "step2"]` | An ordered list exists; every declared step substring appears |
| `callout` | `output.callout: "text, <=120 chars"` | A `> **核心判断/易错点/常见误区/思维停顿**:` block contains the substring |
| `prose` | `output.prose: "original sentence"` + `reason: "non-empty"` | Chapter body contains the substring and `reason` is non-empty |

`must_cover` is not merely "appears somewhere". It must appear in the declared carrier: SVG text, table cells, formula-adjacent variable table, ordered steps, callout, code block, or justified prose.

## Using Detail Cards

- `figure` cards: default to structured representation, not necessarily one SVG per card.
- `example` cards: use in examples, exercises, or worked examples.
- `method` / `operation` cards: use as steps, tables, call chains, or concise prose.
- `exam_tip` cards: consume via `==...==`, callout, or exercise.
- Cards that are truly irrelevant to this chapter may be marked `detail_cards[i].deferred: true`.
- A single skipped `must_cover` item must use `must_cover[j].deferred: true` and `defer_reason`.

Bad:

```markdown
The boot chain is explained only as one long paragraph.
```

Good:

```markdown
![图 3-1：引导链](../assets/figures/ch03-boot-chain.svg)
```

with SVG labels containing `BIOS / bootblocks`, `Master Boot Record`, `LILO / GRUB`, `Linux`, and `User space`.

## Emphasis and Exam Tips

Emphasis is an attention budget. Before adding any marker, decide:

1. **Is this a structural relation?** (flow, comparison, state, classification, layered architecture, variable relations)
   → Use figure, table, formula, or ordered steps — not emphasis.

2. **Is this a judgment readers must remember, or an easy-to-confuse pair?**
   → Use `==高亮==`, a `> **核心判断/易错点/常见误区**` callout, or consume in an exercise.

3. **Is this a local keyword, condition, limit, or counterpoint the reader should briefly notice?**
   → Use `<u>下划线</u>`, or just plain prose.

Hard constraints:

- `<u>...</u>` **cannot** substitute for `exam_tip` consumption. Highlight, callout, or exercise remains the only valid consumption.
- `==...==` wraps the judgment core only, not the long definition around it. Compress the sentence first, then mark.
- Do not stack multiple markers in one clause. If a clause needs both `**term**` and `==judgment==`, split the clause.
- `**term**` vs `<u>keyword</u>`: `**` introduces or anchors a term being defined; `<u>` flags a known term's role in the current sentence (condition, limit, contrast). When in doubt, no marker.

Bad:

```markdown
==复用是操作系统的基本特征==。
```

Good:

```markdown
复用包括 ==时分复用和空分复用==。
分时系统关心的是 <u>交互响应时间</u>，而不是单纯提高吞吐量。
```

An `exam_tip` is consumed only if at least one is true:

- A core assertion or core noun phrase from `summary` appears as `==...==`.
- A core verb/noun phrase appears in a `> **易错点**` or `> **常见误区**` callout.
- The assertion appears in an exercise or answer.

See `spec/style-guide.md` for the full visual emphasis tier table.

## Narrative Order

The usual skeleton is:

```text
foundation -> mechanism -> method/operation -> example -> formula/exam_pattern -> pitfall
```

But concept logic wins over role order. If an example is the best hook, use it early.

## Template Use

Use `spec/chapter-template.md` as a section scaffold, then adapt to the target chapter. Keep:

- front matter with `coverage`
- learning goals
- prior-chapter recall when available
- opening problem
- chapter map
- numbered body sections
- examples, misconceptions, summary, key terms, exercises
- coverage record

## Natural Boundary Language

Forbidden in reader-facing prose:

- `defer`, `future-unknown`, `TODO`, `待补充`
- "本章无法回答" as a heading or apology
- speculative chapter-number notes such as "(将在第 X 章中讲解)" when X is not a real chapter id

Allowed:

- "我们这里先把 X 理解为 Y；至于 X 在并发场景下的更完整含义，等学了同步原语之后回头看会更自然些。"
- "本章只关注 A 视角的 B；C 视角的同样问题会在引入 D 工具后变得清晰。"

## Retrieval Hooks

For each core KP, add useful `retrieval_hooks.bridging` entries:

- contrast with a previous chapter concept
- prediction question pointing to a later section
- cross-chapter application question

## Open Questions

Read `spec/open-questions.md`.

- If this chapter answers an OQ, mark it closed and record chapter/KP.
- If the chapter honestly opens a later-needed question, register a new OQ and list it in front matter.

## Course Skeleton

Update the target chapter from `drafted-pending` to `drafted` in `spec/course-skeleton.md`.

## Before Finish: Self-check

Do not write these answers into the chapter. Ask yourself:

- Did every `visual_reviewed`, `figure`, or `must_cover` card appear in `spec/visual-plans/<stem>.yaml`?
- Does each plan item use `card_ref`, and would it match exactly one card?
- Did I group cards only when grouping improves understanding?
- Did I revise the visual plan after changing a figure/table/callout decision?
- Can a reader grasp the chapter skeleton by scanning headings, figures/tables, key terms, examples, and callouts?
- Are `exam_tip` assertions consumed with `==...==`, callout, or exercise?
- Did I avoid pure prose swallowing an ordered chain, comparison, state machine, formula, or architecture diagram?
- Are SVG labels readable and do they contain the relevant `must_cover` items?
- If a formula appears, did I include a variable table?
- Is emphasis sparse enough to still mean something?

## Run Checks

Prefer:

```bash
python3 scripts/workflow_job.py validate book/chNN-slug.md
```

Or run the checks directly:

```bash
python3 scripts/check_kp_schema.py
python3 scripts/check_chapter_frontmatter.py
python3 scripts/check_detail_coverage.py book/chNN-slug.md
python3 scripts/check_visual_assets.py book/chNN-slug.md
python3 scripts/check_chapter_presentation.py book/chNN-slug.md
python3 scripts/check_open_questions.py
```

Hard checks must pass before finishing.

## Finish the Job

```bash
python3 scripts/workflow_job.py finish \
  --id write-ch08-memory-management-20260526 \
  --applied-to book/ch08-memory-management.md
```

Do not manually edit KP `status`, `queue`, `locked_by`, `reader_notice`, or `applied_to`.

## Report

Report the target, covered KP count, created visual plan path, created figures/tables/callouts, checks run, and next suggested action from `inspect_state.py`. Do not auto-chain the next stage.

## Write Boundaries

- OK: `book/chNN-slug.md`
- OK: `assets/figures/chNN-*.svg`
- OK: `spec/visual-plans/<stem>.yaml`
- OK: `spec/knowledge-points.yaml` only for retrieval hooks and explicit card/item deferrals
- OK: `spec/course-skeleton.md`
- OK: `spec/open-questions.md`
- Do not edit other chapters, supplements, source-index, terminology, style-guide, or chapter-template.
