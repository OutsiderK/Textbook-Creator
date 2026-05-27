# Reference: Initialize

Use when the project directory is empty or `inspect_state.py` reports missing scaffold files.

## Project Template

The skill ships a complete scaffold at `<skill-dir>/assets/project-template/`. To initialize a new project:

```bash
cp -r <skill-dir>/assets/project-template/. <project-root>/
```

The trailing `/.` copies template contents (not the directory itself) into `<project-root>`. The scaffold contains:

```
<project-root>/
  spec/
    knowledge-points.yaml      # empty KP ledger
    source-index.yaml          # empty PPT registry
    workflow-state.yaml        # empty job state
    course-skeleton.md         # low-commitment TOC
    open-questions.md          # OQ tracker
    visual-plans/              # per-chapter visual/presentation contracts
    terminology.md             # generic stub (edit per course)
    style-guide.md             # writing rules + forbidden token list
    chapter-template.md        # chapter section template
    reference-chapter.md       # exemplar for visual density and components
    quality-overrides.yaml     # legacy chapter skip list for presentation checks
    lab-policy.yaml            # enabled: undecided by default
    lab-template.md            # lab README template
  scripts/
    _stage_c_checklist.txt
    inspect_state.py
    workflow_job.py
    check_kp_schema.py
    check_page_risk.py
    render_stage_a_pages.py
    check_chapter_frontmatter.py
    check_detail_coverage.py
    check_visual_assets.py
    check_chapter_presentation.py
    check_open_questions.py
    check_lab.py
    common.py
  assets/figures/
  sources/ppts/                # user drops PPT/PDF here
  book/
    supplements/
  labs/
  docs/
    reference-chapter-annotation.md
```

Do not copy an existing course project as the default initialization path. Copying a real project is only appropriate when the user explicitly asks to fork or duplicate it.

## Goals

- Set up the minimal project skeleton so subsequent stages have files to read and write.
- Confirm the course subject, audience, and initial writing style without pretending to know future PPT content.
- Decide whether labs are part of the textbook, or mark lab policy as undecided.
- Ask lab questions tailored to the course subject.

## Procedure

### 1. Confirm project path

Default to current working directory. If cwd is non-empty and clearly unrelated, ask:

> 我准备在 `<cwd>` 里初始化教材项目。确认这个目录吗？还是另指一个？

If cwd already contains `spec/` or `scripts/`, **stop and ask** before copying—we may overwrite user content. Offer:
- migration mode (copy only missing files), or
- abandon (let user clean up first).

### 2. Gather minimal inputs

Use AskUserQuestion (or natural conversation) to collect:

- **课程名**（必填，将写入 `course-skeleton.md`）。
- **课程语言**（默认中文）。
- **PPT 来源说明**（可选，比如"学期内逐周发布"）。
- **Lab 政策**（4 选 1，详见 [lab-policy-and-design.md](lab-policy-and-design.md)）：
  - `enabled: true` — 确认有 lab，立刻初始化 lab 配置
  - `enabled: false` — 明确不要 lab
  - `enabled: undecided` — 暂不决定，等出现 lab 候选时再问
  - 跳过（等同于 undecided）

**Do NOT ask about chapter list, learning goals, week schedule, etc.** Those are determined by future PPT ingests, not at init. Asking now would violate "低承诺全景"——committing to a structure we don't yet have evidence for.

### 3. Copy template

```bash
cp -r <skill-dir>/assets/project-template/. <project-root>/
```

If files already exist, copy only missing scaffold files after reporting what will be added; **never overwrite user content without explicit approval**.

### 4. Customize per course

Edit (only) these template files for the specific course:

- `spec/course-skeleton.md`：put course name as H1; keep TOC empty.
- `spec/terminology.md`：if the course is a known subject (OS / DB / Compiler / etc.), add 5-10 must-keep terms; otherwise leave as the generic stub.
- `spec/lab-policy.yaml`：set `enabled` from user answer; add `note:` if user said "undecided".

Do NOT pre-fill chapter list. Do NOT add KPs. Those come from PPT ingest.

### 5. Run checks

```bash
cd <project-root>
python3 scripts/inspect_state.py --json
python3 scripts/check_kp_schema.py
```

On a fresh empty project both should report no errors and `actions: []` (or just `ingest` if PPTs already present in `sources/ppts/`).

### 6. Report

To the user:

> 已在 `<project-root>` 初始化教材项目。
> - spec 文件已生成（terminology / style-guide / chapter-template 等可按需修改）
> - 把 PPT 放到 `sources/ppts/` 后，告诉我"摄入"或"更新教材"，我会自动处理。
> - lab 政策：`<decision>`

## Lab Initialization

Use `references/lab-policy-and-design.md`. The generic lab questions in `spec/lab-policy.yaml` are only a template. Rewrite them for the course subject.

Examples:

- **OS textbook**: ask about Linux/WSL/Docker, C/POSIX, Python simulators, xv6/Nachos/NEMU, system-call observation, scheduling, synchronization, memory, filesystems.
- **Database textbook**: ask about SQL engine, PostgreSQL/MySQL/SQLite, transaction labs, query planning, indexing, benchmark data.
- **Compiler textbook**: ask about parser generators, LLVM, interpreters, type checking, optimization passes.

If the user is unsure, set `enabled: undecided` and continue. Do not block non-lab writing unless the next chapter clearly needs a lab decision.

## Write Boundaries

Only the files listed in "Project Template" above. Don't write `book/chXX.md` or `docs/ingest-*.md` here.

## Don't

- 不要在 init 时填章节大纲、学习目标、周排程。这些等 PPT 来了在 rebalance 阶段才确定。
- 不要询问"这门课打算讲什么"——那是 Agent 不该主观推断的部分。
- 不要在已有非空项目上盲目复制 template，可能覆盖用户内容。
- 不要在 init 时调用 `workflow_job.py`——还没有 KP 可锁。
