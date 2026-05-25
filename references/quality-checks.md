# Reference: Quality Checks

Map of scripts to severity and when to run them. Loaded when:

- A stage completes (run relevant checks before announcing success)
- User says "检查状态 / 跑 check"
- `inspect_state.py` reports `actions: []` (then this reference dictates the final pass)

All scripts assume you're running from `<project-root>`. Scripts read their own files via `common.py`.

## Severity model

| Severity | Meaning |
|---|---|
| **hard** | Failure must stop the stage. Don't `workflow_job.py finish`; abort or fix first. |
| **soft** | Failure produces a warning. Report to user but proceed. |

## Script Map

| Script | When to run | Severity | What it validates |
|---|---|---|---|
| `inspect_state.py` | Every skill invocation, after every stage | (state report, not pass/fail) | Project state |
| `check_kp_schema.py` | After A, B, C, D | **hard** | knowledge-points.yaml schema, status/queue rules, role/card type enums, id uniqueness |
| `check_chapter_frontmatter.py` | After C, D | **hard** | Chapter file front-matter schema; coverage IDs match knowledge-points.yaml; forbidden tokens absent from prose |
| `check_open_questions.py` | After B, C, D | **soft** | open-questions.md structural; cross-refs to chapters/KPs |
| `check_lab.py` | After lab module | **hard** for code labs (verify.sh must pass); **soft** for observation labs |

## Per-Stage Required Checks

### After Init

```bash
python3 scripts/check_kp_schema.py        # should trivially pass on empty ledger
python3 scripts/inspect_state.py --json   # should report initialized: true, actions: []
```

### After Stage A (Ingest)

```bash
python3 scripts/check_kp_schema.py        # hard
```

Hard failure here usually means the KP yaml was corrupted by partial write. Roll back if needed.

### After Stage B (Rebalance)

```bash
python3 scripts/check_kp_schema.py             # hard
python3 scripts/check_open_questions.py        # soft
```

Validate that every queued KP has consistent `queue.action`, `queue.target`, `queue.reason` (only when action=hold), and `reader_notice` (=needed only when action=patch_chapter).

### After Stage C (Write Chapter)

`workflow_job.py finish` runs **before** checks; checks validate the post-finish state.

```bash
python3 scripts/check_kp_schema.py             # hard
python3 scripts/check_chapter_frontmatter.py   # hard
python3 scripts/check_open_questions.py        # soft
```

Hard fail patterns:

- Coverage records reference KPs that aren't `status: applied` or don't include this chapter in `applied_to`
- Front-matter missing required fields
- Chapter file uses forbidden tokens: `defer`, `future-unknown`, `TODO`, `待补充`, `新增`

### After Stage D (Integrate Supplement)

```bash
python3 scripts/check_kp_schema.py             # hard
python3 scripts/check_chapter_frontmatter.py   # hard
python3 scripts/check_open_questions.py        # soft
```

Additionally check:

- Each KP with `reader_notice: published` has a corresponding `book/supplements/chMM-*.md` file
- Supplement files don't contain date/version markers (`v1`, `2026-`, `本次更新`)

### After Lab Module

```bash
python3 scripts/check_lab.py labs/labXX-slug/   # hard for code labs
```

## "All clean" 状态

If `inspect_state.py` returns `actions: []` AND no workflow.current_job, run the full pass:

```bash
python3 scripts/check_kp_schema.py
python3 scripts/check_open_questions.py
python3 scripts/check_chapter_frontmatter.py
python3 scripts/check_lab.py
```

报告：

```
项目状态: 全部 clean ✓
  KPs: 总 N，applied N
  章节: M 章，全部 drafted
  Supplements: S 份
  Labs: L 个 (全部 verify 通过)
  Open Questions: O 条 open / Q 条已解决

下一步可以等下一份 PPT 来。
```

## 报告格式

每次 check 后给用户一个紧凑摘要：

```
✓ check_kp_schema  (89 KPs, 0 errors)
✗ check_chapter_frontmatter book/ch08-memory-management.md
    - 覆盖记录引用 OSPPT-CH08-XYZ, 但 ledger 中该 KP 的 applied_to 不包含 book/ch08-memory-management.md
⚠ check_open_questions (1 warning)
    - OQ-004 状态为 closed 但缺 关闭_KP 字段
```

`hard fail` 用 `✗`，`warning` 用 `⚠`，pass 用 `✓`。Hard fail 必须修复后再宣告 stage 完成。

## 自动修复 vs 手动修复

| 错误类型 | 处理 |
|---|---|
| YAML 解析失败 | 报告精确行号，等用户修 |
| KP id 引用不存在 | 报告，等用户决定（是 typo 还是该 KP 被错删） |
| Front-matter 缺字段 | 可自动补 `[]` 或 `null`，但补完要提示用户 |
| 正文含禁词 | 报告位置，等 Agent 重写那段（Stage C/D 内部自检阶段） |
| Supplement 含日期 | 报告，让 Agent 自动剔除 |
| KP locked_by 与 current_job 不一致 | 报告 warning；如果 workflow-state 已无 job，提示用 `workflow_job.py abort` 或手动清锁 |

**默认保守**：除非禁词剔除这种零风险动作，否则报告 + 等用户/Agent 决定，不要悄悄改文件。

## Don't

- 不要在 check 中改 spec 文件的语义内容——check 只验证，不"修复语义"。
- 不要把 soft 警告升级为阻塞错误。
- 不要把同一类错误重复打印 100 次——同类多个失败做聚合摘要。
- 不要把 status 字段的修复交给 check 脚本——它由 `workflow_job.py` 负责。check 只读不写。
