# Reference: Initialize

Use when the project directory is empty or missing `spec/`. The skill enters this stage automatically when `inspect_state.py` reports `initialized: false`.

## Goal

Set up the minimal project skeleton so that subsequent stages have files to read and write. Do NOT pre-fill knowledge points, chapters, or panorama details.

## Project Layout to Create

```
<project-root>/
  inputs/                       # user drops PPTs here
  spec/
    source-index.yaml           # PPT registry; starts empty
    knowledge-points.yaml       # KP ledger; starts empty
    course-skeleton.md          # current TOC + status; starts with course name only
    open-questions.md           # OQ tracker; starts empty
    terminology.md              # from template
    style-guide.md              # from template
    chapter-template.md         # from template
    lab-policy.yaml             # ONLY if user opts in
  book/
    supplements/                # empty dir
  docs/                         # empty dir
```

`labs/` is **not** created unless lab policy is `enabled: true` or `enabled: undecided`.

## Process

### 1. Confirm project path

Default to current working directory. If cwd is non-empty and clearly unrelated, ask:

> 我准备在 `<cwd>` 里初始化教材项目。确认这个目录吗？还是另指一个？

### 2. Gather minimal inputs

Use AskUserQuestion (or natural conversation) to collect:

- **课程名**（必填，将写入 `course-skeleton.md`）。
- **课程语言**（默认中文）。
- **PPT 来源说明**（可选，比如 "学期内逐周发布"）。
- **Lab 政策**（4 选 1，详见 [lab-policy-and-design.md](lab-policy-and-design.md)）：
  - `enabled: true` — 确认有 lab，立刻初始化 lab 配置
  - `enabled: false` — 明确不要 lab
  - `enabled: undecided` — 暂不决定，等出现 lab 候选时再问
  - 跳过（等同于 undecided）

**Do NOT ask about chapter list, learning goals, week schedule, etc.** Those are determined by future PPT ingests, not at init. Asking now would violate "低承诺全景" — committing to a structure we don't yet have evidence for.

### 3. Write files

Copy from `assets/templates/`:
- `terminology.md` → `spec/terminology.md`
- `style-guide.md` → `spec/style-guide.md`
- `chapter-template.md` → `spec/chapter-template.md`

Create fresh:
- `spec/source-index.yaml`:
  ```yaml
  sources: []
  next_batch_id: 1
  ```
- `spec/knowledge-points.yaml`:
  ```yaml
  knowledge_points: []
  ```
- `spec/course-skeleton.md`:
  ```markdown
  # <课程名>

  > 本目录随课程进展同步更新。每章标当前状态。

  ## 章节

  (尚无章节)
  ```
- `spec/open-questions.md`:
  ```markdown
  # Open Questions

  > 跨章追踪的"尚未深入/尚未解决的问题"。内部使用，不暴露给读者。

  ## 当前 open

  (尚无)

  ## 已解决

  (尚无)
  ```

If lab policy chosen, copy `lab-policy.yaml` template; otherwise skip.

Create empty dirs: `inputs/`, `book/supplements/`, `docs/`.

### 4. Report

To the user:

> 已在 `<project-root>` 初始化教材项目。
> - spec 文件已生成（terminology / style-guide / chapter-template 等可按需修改）
> - 把 PPT 放到 `inputs/` 后，告诉我"摄入"或"更新教材"，我会自动处理。
> - lab 政策：`<decision>`

## Write Boundaries

Only the files listed in "Project Layout to Create" above. Don't write `book/chXX.md` or `docs/ingest-*.md` here.

## In-Progress Marker

Init is idempotent (template copies + empty file creation), so the in-progress marker is optional. If used:

```yaml
stage: initialize
batch: 0
target: <project-root>
```

Clear on success.

## Checks After

Run `scripts/check_kp_schema.py <project-root>` — should pass trivially (empty ledger is valid).

## Don't

- 不要在 init 时填章节大纲、学习目标、周排程。这些等 PPT 来了在 rebalance 阶段才确定。
- 不要询问"这门课打算讲什么"——那是 Agent 不该主观推断的部分。
- 不要在已有非空项目上盲目运行 init。检测到 `spec/` 已存在则停止并问用户："spec/ 已存在，是否进入 migration 模式（保留现有，仅补齐缺失）还是放弃 init？"
