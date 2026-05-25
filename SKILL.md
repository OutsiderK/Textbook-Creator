---
name: online-course-textbook
description: Use when building or evolving a textbook from an ongoing course's incremental PPT/PDF releases. Trigger when the user provides new lecture PPTs (e.g. "把这份 PPT 加进教材"), asks to write/update a chapter ("写第 X 章""把第 X 章补完整"), initializes a textbook project, or asks about the project's current state ("继续更新教材""检查状态"). The skill handles the full pipeline (ingest, rebalance, write, supplement, lab) through state-driven routing — the user speaks naturally and the skill decides the next stage.
metadata:
  short-description: Online-course-driven textbook construction with state-driven stage routing
---

# Online Course Textbook

Use this skill for building a textbook from an ongoing course where PPTs arrive incrementally (week by week). The workflow has 5 stages plus an optional lab module, but stages are **auto-routed by `scripts/inspect_state.py`** — the user does not need to invoke each stage manually.

The skill has one public interface. Do not ask the user to invoke internal stages. Route their natural request to the right stage after inspecting project state.

## The Core Principles (always apply)

1. **单调积累** — 已有知识点不推翻，只扩展、连接、细化。
2. **内外分层** — 内部追溯/审计/状态机；读者文本自然/连贯/像成书。
3. **主稿演进** — 主稿吸收新知识，不在正文留更新痕迹；supplement 是给已读读者的通知，不是第二正文。
4. **延迟归属** — 不确定的 KP 留 hold（`queue.action: hold` + `queue.reason`），不硬塞章节。
5. **聚簇切分** — 章节边界由概念关联度决定；数量规则只做软提醒。
6. **应试细节保留** — PPT 里的方法/技巧/例题/图表/易错点抓进 KP 的 `detail_cards`。

## Project Root

Resolve `PROJECT_ROOT` before every action:

1. If the user provides a path, use that path.
2. Else if the current directory contains `spec/` and `scripts/inspect_state.py`, use the current directory.
3. Else search upward from the current directory for a directory containing `spec/` and `scripts/inspect_state.py`.
4. Else if the user asks to initialize a new project, use the current directory after confirming it is the intended destination.
5. Otherwise ask the user to confirm the project directory.

Validate the resolved root before modifying files:

- Existing projects must contain `spec/`, `scripts/inspect_state.py`, and `scripts/common.py`.
- Stage C and Stage D additionally require `scripts/workflow_job.py`.
- If validation fails, report the missing files and ask whether to initialize, repair from `<skill-dir>/assets/project-template/`, or use another directory.

Copied projects are independent project roots. Never operate on the original project unless its path was explicitly selected.

## Always Start With State

1. Resolve and validate `PROJECT_ROOT`.
2. Change to `PROJECT_ROOT`.
3. Run `python3 scripts/inspect_state.py --json`.
4. The output has these key fields:
   - `actions[]` — proposed next actions in priority order (the SSOT for routing)
   - `requires_proposal` — true if multiple actions exist or workflow is interrupted; you MUST propose-confirm
   - `workflow.current_job` / `workflow.interrupted` — if present, an earlier stage was interrupted
   - `knowledge_points.status_counts`, `queued_actions`, `locks` — KP state breakdown
   - `sources.unindexed` — PPT files not yet in source-index.yaml
5. Consume `actions[]` in order. For each, decide whether the user's intent matches (override mode) or whether to propose the highest-priority action and wait for approval (auto mode).

**Do not** maintain a parallel routing table in this document. `inspect_state.py` is the routing spec; this section describes how to consume its output.

## Behavior Rule 1: Propose, Don't Execute (auto mode)

When `requires_proposal: true` or when the user said something vague ("继续更新教材""根据最新 PPT 更新"), **always announce the proposed action and wait for the user's go-ahead** before executing — even when only one action is pending.

Template:

> **当前状态：**
> - pool 中有 3 个 KP（来自 ch06.pdf, ch07.pdf）
> - ch07 草稿待生成
> - 新 PPT `ch08.pdf` 未摄入
>
> **按 `inspect_state.py` 的下一步建议，我将先做 Stage A：摄入 ch08.pdf。** 是否批准？
>
> （若要换顺序，请明确说"先写 ch07"或"只摄入 ch08"。）

After confirmation, execute that ONE stage. Then re-run `inspect_state.py` and propose the next step (do not chain stages silently).

## Behavior Rule 2: Explicit Override (user-driven mode)

When the user gives an **explicit, scoped instruction**, do ONLY that action. After the action finishes, re-inspect state and **report new state without auto-continuing** — wait for the user.

Override triggers (non-exhaustive):

| User says | Do only |
|---|---|
| "摄入 X.pdf" / "只摄入这份 PPT" / "先把 X 处理一下" | Stage A on the specified PPT |
| "把这几个 PPT 都摄入" | Stage A on each PPT, in order, then stop |
| "写第 N 章" / "生成 chXX" | Stage C on the specified chapter |
| "补充第 N 章" / "把 chXX 补一下" | Stage D on the specified chapter |
| "重平衡" / "做 rebalance" | Stage B only |
| "检查状态" / "跑 check" | quality-checks |
| "初始化" / "init this project" | initialize only |
| "设计实验" / "搞一下 lab" | Lab module |

The defining signal of an override is **scope specificity** — the user names a target (a PPT, a chapter, a stage), not a vague "继续".

## Behavior Rule 3: Interrupt / Recovery

`scripts/workflow_job.py` is the lock for Stage C and Stage D edits. It writes `spec/workflow-state.yaml.current_job` + sets `locked_by` / `lock_stage` / `lock_target` on each affected KP.

If `inspect_state.py` reports `workflow.interrupted: true`, **before doing anything else**, prompt the user:

> **检测到上次 Stage `write_chapter` 在写 `book/ch07-scheduling.md` 时中断**
> （job id `ch07-write-003`，锁定 KP：OSPPT-CH04-FCB, OSPPT-CH04-DIRECTORY, ...）
>
> 选项：
>   1. **继续** — 检查目标文件状态后从中断点续写，然后正常 `workflow_job.py finish`
>   2. **丢弃** — `python3 scripts/workflow_job.py abort --id <job-id> --to-status queued`，KP 回到 queued 状态
>   3. **取消** — 不做任何改动，等待你的下一步指示

Recovery semantics by stage (see each reference for details):

- **Stage A / B**: no `workflow_job` lock. They are yaml-append/rewrite stages, safe to re-run idempotently.
- **Stage C / D**: locked by `workflow_job start`; resume by completing the edits and calling `workflow_job finish`, or abort with `workflow_job abort`.

## State Model

KP status is one of:

- `pool` — 已知但未分配（fresh from ingest）。**没有 `queue` 字段。**
- `queued` — Stage B 决定了去向，有 `queue.action`：
  - `queue.action: new_chapter` + `queue.target: book/chNN-...` → Stage C 写新章
  - `queue.action: patch_chapter` + `queue.target: book/chMM-...` + `reader_notice: needed` → Stage D 补旧章
  - `queue.action: hold` + `queue.reason: <enum>` → 暂留等候，不进章
- `applied` — 已写入主稿。`queue` 字段被清空，`applied_to: [book/chNN-...]` 记录归属（list，支持一 KP 多章）。

`queue.reason` 枚举（仅 `action: hold` 时使用，schema 强制）：

- `awaiting_followup` — 等后续 PPT 把同主题补完整
- `bridging_undefined` — 跨多个潜在章节，需要看到更多关联 KP 才能定
- `enrichment_only` — 是某未来章的扩展材料，主章节核心还没出现
- `manual_review` — 复杂度足够高，建议用户提示后再分配

`reader_notice` 是独立维度：

- `none` — 默认
- `needed` — Stage B 标记 patch_chapter 时设置
- `published` — Stage D `workflow_job.py finish --reader-notice published` 后自动设置

Do not invent additional status values. Do not store reader-notice info in `status`.

## Interruption Safety

Before Stage C or Stage D edits, start a job:

```bash
python3 scripts/workflow_job.py start \
  --id <job-id> --stage <write_chapter|integrate_supplement> \
  --target book/chNN-slug.md --batch <batch> \
  --queue-action <new_chapter|patch_chapter> \
  --kps <KP-ID...>
```

This atomically:
1. Sets `spec/workflow-state.yaml.current_job` to the new job.
2. Sets `locked_by`, `lock_stage`, `lock_target` on each KP.
3. Refuses to start if another job is already active.

Finish only after all edits AND quality checks pass:

```bash
python3 scripts/workflow_job.py finish --id <job-id> \
  --applied-to book/chNN-slug.md \
  [--reader-notice published]   # Stage D only
```

This flips each KP's status `queued → applied`, clears `queue` + lock fields, appends `applied_to`, and archives the job to `history`.

Abort if the user discards mid-stage:

```bash
python3 scripts/workflow_job.py abort --id <job-id> --to-status queued
# or --to-status pool if Stage B's queue assignment was also wrong
```

Stage A and Stage B do **not** use `workflow_job.py`. They edit yaml atomically (single rewrite) and are safe to re-run idempotently. The asymmetry is intentional: `workflow_job` protects against half-written chapter prose + half-flipped KP status, which is a real failure mode for Stage C/D but not for ingest/rebalance.

## Reader-Facing Text

Main chapters must read like a polished textbook. Do not expose workflow vocabulary (`pool`, `queued`, `rebalance`, `defer`, `future-unknown`, `TODO`, `待补充`, `新增`, dated update markers). Use natural boundary language instead — see `spec/style-guide.md`.

`check_chapter_frontmatter.py` scans for forbidden tokens; chapter completion fails if any are present.

## Write Boundaries (per stage)

Each stage may only modify the files its reference document declares:

- **Stage Init** — `spec/*` (template files from `<skill-dir>/assets/project-template/`)
- **Stage A (Ingest)** — `spec/knowledge-points.yaml` (append), `spec/source-index.yaml`, `docs/ingest-<batch>.md`
- **Stage B (Rebalance)** — `spec/knowledge-points.yaml` (status/queue/reader_notice flips), `spec/course-skeleton.md`, `spec/open-questions.md`, `docs/rebalance-<batch>.md`
- **Stage C (Write)** — `book/chNN-slug.md`, `assets/figures/chNN-*.svg`, `spec/knowledge-points.yaml` (only `retrieval_hooks.bridging` + `detail_cards[i].deferred` — other fields via `workflow_job`), `spec/course-skeleton.md`, `spec/open-questions.md`
- **Stage D (Integrate Supplement)** — `book/chMM-slug.md`, `book/supplements/chMM-*.md`, `assets/figures/chMM-*.svg`, `spec/open-questions.md` (status/reader_notice via `workflow_job`)
- **Lab** — `labs/labXX-slug/*`, `spec/lab-policy.yaml` (init only)

If a stage needs to modify a shared spec file (`terminology.md`, `style-guide.md`, `chapter-template.md`, `lab-policy.yaml` outside init), **stop and ask the user** before writing.

## Reference Index (load on demand)

| Reference | Loaded when |
|---|---|
| `references/initialize.md` | Stage Init |
| `references/ingest.md` | Stage A |
| `references/rebalance.md` | Stage B |
| `references/write-chapter.md` | Stage C |
| `references/integrate-supplement.md` | Stage D |
| `references/lab-policy-and-design.md` | Lab module triggered |
| `references/quality-checks.md` | After any stage; or "check" override |

Do not preload references. Following progressive-disclosure: load only the one needed for the current action.

## Do NOT

- 不要在草稿正文使用 `defer`、`future-unknown`、`TODO`、`新增`、`待补充` 等工作流术语。诚实承认无法深入的内容要用自然散文。
- 不要在 supplement 文档写日期、版本号、`v1.0`、"本次新增" 等时间标记。supplement 永远读起来像"一直就在那"。
- 不要自动跳过 propose-confirm（除非在显式 override 模式且操作目标已被用户指定）。
- 不要自动链式触发下游 stage —— 每完成一个 stage 都要 re-inspect + propose 下一个。
- 不要在中断态直接覆盖半成品文件——先 resume 或 abort。
- 不要手动 flip KP `status` / `queue` / `reader_notice` / `applied_to`——Stage C/D 用 `workflow_job.py`；Stage A/B 直接编辑 yaml 但要遵循 schema。
- 不要在本 SKILL.md 里复制 `inspect_state.py` 的路由优先级——脚本是 SSOT。
- 不要修改 `terminology.md`、`style-guide.md`、`chapter-template.md`、`lab-policy.yaml` 等共享 spec 文件，除非用户明确批准。
