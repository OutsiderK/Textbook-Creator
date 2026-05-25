# Reference: Quality Checks

Map of scripts to severity and when to run them. Loaded when:
- A stage completes (run relevant checks before announcing success)
- User says "检查状态 / 跑 check"
- `inspect_state.py` reports `all clean` (then this reference dictates the final pass)

## Severity model

| Severity | Meaning |
|---|---|
| **hard** | Failure must stop the stage. Don't commit/announce success. Fix or roll back. |
| **soft** | Failure produces a warning. Report to user but proceed. |

## Script Map

| Script | When to run | Severity | What it validates |
|---|---|---|---|
| `inspect_state.py` | Every skill invocation, after every stage | (state report, not pass/fail) | Project state |
| `check_kp_schema.py` | After A, B, C, D | **hard** | knowledge-points.yaml schema, status values, id uniqueness, link integrity |
| `check_chapter_frontmatter.py` | After C, D | **hard** | Chapter file front-matter schema; coverage IDs match knowledge-points.yaml |
| `check_open_questions.py` | After B, C, D | **soft** | open-questions.md structural; cross-refs to chapters/KPs |
| `check_lab.py` | After lab module | **hard** for code labs (verify.sh must pass); **soft** for observation labs |

## Per-Stage Required Checks

### After Init

```bash
python3 scripts/check_kp_schema.py <project-root>      # should trivially pass on empty ledger
```

### After Stage A (Ingest)

```bash
python3 scripts/check_kp_schema.py <project-root>      # hard
```

Hard failure here usually means the KP yaml was corrupted by partial write. Roll back if needed.

### After Stage B (Rebalance)

```bash
python3 scripts/check_kp_schema.py <project-root>      # hard
python3 scripts/check_open_questions.py <project-root> # soft
```

Validate that every queued KP has `action`, `applied_to`, and consistent `reader_notice`.

### After Stage C (Write Chapter)

```bash
python3 scripts/check_kp_schema.py <project-root>             # hard
python3 scripts/check_chapter_frontmatter.py book/chXX-*.md  # hard
python3 scripts/check_open_questions.py <project-root>       # soft
```

Hard fail patterns:
- Coverage records reference KPs that aren't `status: applied` or aren't `applied_to: chXX` in the ledger
- Front-matter missing required fields
- Chapter file uses forbidden tokens: `defer`, `future-unknown`, `TODO`, `待补充`, `新增`

### After Stage D (Patch Chapter)

```bash
python3 scripts/check_kp_schema.py <project-root>              # hard
python3 scripts/check_chapter_frontmatter.py book/chMM-*.md   # hard
python3 scripts/check_open_questions.py <project-root>        # soft
```

Additionally check:
- Each KP with `reader_notice: published` has a corresponding `book/supplements/chMM-*.md` file
- Supplement files don't contain date/version markers (`v1`, `2026-`, `本次更新`)

### After Lab Module

```bash
python3 scripts/check_lab.py labs/labXX-slug/   # hard for code labs
```

## "全部 clean" 状态

如果 `inspect_state.py` 返回 `next_action: check_state`（没有 pool / queued / pending_ppts），运行全套：

```bash
python3 scripts/check_kp_schema.py <project-root>
python3 scripts/check_open_questions.py <project-root>
for chapter in book/ch*.md; do
  python3 scripts/check_chapter_frontmatter.py "$chapter"
done
for lab in labs/lab*/; do
  python3 scripts/check_lab.py "$lab"
done
```

报告：

```
项目状态: 全部 clean ✓
  KPs: 总 N，应用 N
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
    - 覆盖记录引用 OSPPT-CH08-XYZ, 但 ledger 中该 KP 的 applied_to 是 ch09
  build/...
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

**默认保守**：除非禁词剔除这种零风险动作，否则报告 + 等用户/Agent 决定，不要悄悄改文件。

## 不要

- 不要在 check 中改 spec 文件的语义内容 —— check 只验证，不"修复语义"。
- 不要把 soft 警告升级为阻塞错误。
- 不要把同一类错误重复打印 100 次 —— 同类多个失败做聚合摘要。
