---
name: online-course-textbook
description: Use when building or evolving a textbook from an ongoing course's incremental PPT/PDF releases. Trigger when the user provides new lecture PPTs (e.g. "把这份 PPT 加进教材"), asks to write/update a chapter ("写第 X 章""把第 X 章补完整"), initializes a textbook project, or asks about the project's current state ("继续更新教材""检查状态"). The skill handles the full pipeline (ingest, rebalance, write, supplement, lab) through internal state-driven routing — the user speaks naturally and the skill decides the next stage.
metadata:
  short-description: Online-course-driven textbook construction with state-driven stage routing
---

# Online Course Textbook

Use this skill for building a textbook from an ongoing course where PPTs arrive incrementally (week by week). The workflow has 5 stages plus an optional lab module, but stages are **auto-routed based on project state and user intent** — the user does not need to invoke each stage manually.

## The Core Principles (always apply)

1. **单调积累** — 已有知识点不推翻，只扩展、连接、细化。
2. **内外分层** — 内部追溯/审计/状态机；读者文本自然/连贯/像成书。
3. **主稿演进** — 主稿吸收新知识，不在正文留更新痕迹；supplement 是给已读读者的通知，不是第二正文。
4. **延迟归属** — 不确定的 KP 留 pool，不硬塞章节。
5. **聚簇切分** — 章节边界由概念关联度决定；数量规则只做软提醒。
6. **应试细节保留** — PPT 里的方法/技巧/例题/图表/易错点抓进 KP 的 `detail_cards`。

## Required First Step: Inspect State

Before any action, run:

```bash
python3 <skill-dir>/scripts/inspect_state.py <project-root>
```

The script returns a state report. Key fields:
- `initialized` — bool
- `in_progress` — non-empty if a previous stage was interrupted
- `pending_ppts` — PDFs in `inputs/` not yet in `spec/source-index.yaml`
- `kp_status` — counts/ids by `{pool, queued_new, queued_patch, applied}`
- `pending_supplements` — KPs with `reader_notice: needed`
- `suggested_next_action` — the highest-priority action under default routing

**`<project-root>` is the textbook project directory, not this skill directory.** Default to current working directory if it contains `spec/` or `inputs/`; otherwise ask the user.

## Default Stage Routing (priority order)

| Priority | Trigger | Action | Reference |
|---|---|---|---|
| 0 | `spec/.in-progress.yaml` exists | Resume-or-discard prompt | (this file) |
| 1 | `spec/` missing or empty | Initialize | `references/initialize.md` |
| 2 | `pending_ppts` non-empty | Stage A: Ingest | `references/ingest.md` |
| 3 | `kp_status.pool` non-empty | Stage B: Rebalance | `references/rebalance.md` |
| 4 | `kp_status.queued_new` non-empty | Stage C: Write chapter | `references/write-chapter.md` |
| 5 | `kp_status.queued_patch` non-empty | Stage D: Patch chapter | `references/patch-chapter.md` |
| 6 | Lab pending (policy enabled + chapter needs lab) | Lab | `references/lab-policy-and-design.md` |
| 7 | All clean | Run checks | `references/quality-checks.md` |

Higher priority blocks lower (ingest before rebalance before write, etc.).

## Behavior Rule 1: Propose, Don't Execute

After running `inspect_state.py`, **always announce the proposed action and wait for the user's go-ahead** before executing — even when only one action is pending.

Template:

> **当前状态：**
> - pool 中有 3 个 KP（来自 ch06.pdf, ch07.pdf）
> - ch07 草稿待生成
> - 新 PPT `ch08.pdf` 未摄入
>
> **按默认优先级，我将先做 Stage A：摄入 ch08.pdf。** 是否批准？
>
> （若要换顺序，请明确说"先写 ch07"或"只摄入 ch08"。）

After confirmation, execute that ONE stage. Then re-run `inspect_state.py` and propose the next step (do not chain stages silently).

## Behavior Rule 2: Explicit Override (User-Driven Mode)

When the user gives an **explicit, scoped instruction**, do ONLY that action. Skip the default router. After the action finishes, re-inspect state and **report new state without auto-continuing** — wait for the user.

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

The defining signal of an override is **scope specificity** — the user names a target (a PPT, a chapter, a stage), not a vague "继续". Pool draining, downstream stage triggering, or auto-rebalance must NOT happen in override mode.

When in **auto mode** (user said "继续更新教材""根据最新 PPT 更新课本""继续处理未完成内容" without specifics), follow the default routing — but still propose-confirm per step (Rule 1).

## Behavior Rule 3: Interrupt / Recovery

Before starting any stage that modifies files, write `spec/.in-progress.yaml`:

```yaml
stage: write-chapter      # ingest | rebalance | write-chapter | patch-chapter | lab
batch: 003                # batch id of the current operation
target: ch07-scheduling   # chapter id, PPT path, or KP cluster id
kp_ids:                   # KPs locked by this stage (status will roll back if discarded)
  - OSPPT-CH04-FCB
  - OSPPT-CH04-DIRECTORY
notes: |
  Stage C drafting ch07 from rebalance-003 output.
  KP statuses pre-stage: queued (will become applied on success).
```

On successful stage completion, **delete** this file. The stage reference for each stage describes its commit/cleanup point.

If `inspect_state.py` reports `in_progress` non-empty on startup, that's an interrupted stage. **Before doing anything else**, prompt the user:

> **检测到上次 Stage `write-chapter` 在写 `ch07-scheduling` 时中断**
> （batch 003，涉及 5 个 KP：OSPPT-CH04-FCB, OSPPT-CH04-DIRECTORY, ...）
>
> 选项：
>   1. **继续** — 检查目标文件状态后从中断点续写
>   2. **丢弃** — 删除半成品文件，KP 状态回滚到 queued，删除 `.in-progress.yaml`
>   3. **取消** — 不做任何改动，等待你的下一步指示

Recovery semantics per stage:

- **ingest**: if `source-index.yaml` was updated atomically last, re-run is safe (idempotent dedup). If half-updated, restore from git or roll back source-index entry first.
- **rebalance**: regenerate from current pool state (no half-state can persist in KP files if rebalance writes atomically — see `references/rebalance.md`).
- **write-chapter**: if `book/chXX.md` exists with content, continue from there; otherwise restart from template.
- **patch-chapter**: if both main chapter changes and supplement file are present, verify consistency; if only one, complete the other or roll back.

## Project Path Detection

The skill operates on a **textbook project directory**, which is separate from this skill's installation directory. Determine project path by:

1. If current working directory contains `spec/` or `inputs/`, use it.
2. If current working directory is empty or has only a few stray files, ask "在哪个目录初始化？（默认：当前目录）"
3. Otherwise ask "请确认项目目录"

## Write Boundaries (per stage)

Each stage may only modify the files its reference document declares. Cross-stage modifications are forbidden:

- Stage A (Ingest) may write: `spec/knowledge-points.yaml` (append/merge), `spec/source-index.yaml`, `docs/ingest-{batch}.md`
- Stage B (Rebalance) may write: `spec/knowledge-points.yaml` (status/action/applied_to/reader_notice fields only), `spec/course-skeleton.md`, `spec/open-questions.md`, `docs/rebalance-{batch}.md`
- Stage C (Write) may write: `book/chXX-slug.md` (the target chapter), `spec/knowledge-points.yaml` (status flip queued→applied only), `spec/course-skeleton.md` (status of this chapter), `spec/open-questions.md`
- Stage D (Patch) may write: `book/chXX-slug.md` (the target chapter, may restructure for flow), `book/supplements/chXX-{kp-slug}.md`, `spec/knowledge-points.yaml` (status flip + reader_notice→published), `spec/open-questions.md`

If a stage needs to modify a shared spec file (terminology.md, style-guide.md, chapter-template.md, lab-policy.yaml), **stop and ask the user** before writing.

## Do NOT

- **不要**在草稿正文使用 `defer`、`future-unknown`、`TODO`、`新增`、`待补充` 等工作流术语。诚实承认无法深入的内容要用自然散文（"对并发场景下的具体协议，等到我们对线程和锁有了足够的工具之后再回来"）。
- **不要**在 supplement 文档写日期、版本号、`v1.0`、"本次新增" 等时间标记。supplement 永远读起来像"一直就在那"。
- **不要**自动跳过 propose-confirm（除非在显式 override 模式且操作目标已被用户指定）。
- **不要**自动链式触发下游 stage —— 每完成一个 stage 都要 re-inspect + propose 下一个。
- **不要**在中断态直接覆盖半成品文件。
- **不要**修改未声明可改的 spec 文件。

## Reference Index (load on demand)

| Reference | Loaded when |
|---|---|
| `references/initialize.md` | Stage Init |
| `references/ingest.md` | Stage A |
| `references/rebalance.md` | Stage B |
| `references/write-chapter.md` | Stage C |
| `references/patch-chapter.md` | Stage D |
| `references/lab-policy-and-design.md` | Lab module triggered |
| `references/quality-checks.md` | After any stage; or "check" override |

Do not preload references. Following progressive-disclosure: load only the one needed for the current action.
