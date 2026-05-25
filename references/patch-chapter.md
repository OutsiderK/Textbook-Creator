# Reference: Stage D — Patch Chapter

Trigger: `inspect_state.py` reports `kp_status.queued_patch` non-empty。或用户说"补充第 N 章 / 把 chXX 补一下"。

> **Stage D 的座右铭：通知。** 主稿吸收新 KP（必要时为流畅性微调结构）。**同时**写一份独立的"知识点专题"补充文档，给已读过旧版的读者一个聚焦阅读入口。主稿不留任何"新增"痕迹；supplement 不写日期或版本号。

## Input

- `spec/knowledge-points.yaml`（特别是 `action: patch_chapter` + `applied_to: chMM-slug` + `reader_notice: needed` 的 KP）
- 目标章节 `book/chMM-slug.md`（已存在）
- `spec/style-guide.md`
- `spec/terminology.md`

## Output

- `book/chMM-slug.md` —— **修改**：在自然位置插入新内容，必要时微调相邻小节使整体更流畅。**不留更新痕迹**。
- `book/supplements/chMM-<kp-slug>.md` —— 每个 patch KP 一份独立专题文档。
- KP 状态：`status: queued → applied`，`reader_notice: needed → published`，清掉 `action` 字段。
- `spec/open-questions.md` —— 如有相关 OQ 闭合则登记。

**Do NOT touch**: source-index, terminology, style-guide, chapter-template, 其他章节, 任何 Stage B 的输出（除上面允许的状态翻转）。

## In-Progress Marker

```yaml
stage: patch-chapter
batch: 003
target: ch07-storage-foundations
kp_ids:
  - OSPPT-CH08-TLB-DETAILS
  - OSPPT-CH08-ADDR-TRANSLATION-DEEP
notes: "Stage D patching ch07 with 2 KPs from rebalance-003"
```

Recovery:
- 主稿和 supplement 都已生成 → 清掉 marker，stage 视为完成
- 仅主稿改了，supplement 缺失 → 补 supplement
- 仅 supplement 在，主稿未改 → 补主稿
- 两者都未动 → 重启 stage

## Process

### 1. 读目标章节

完整读 `book/chMM-slug.md`，理解：
- 当前主线是什么
- 哪些小节已存在
- 章末覆盖记录、关键术语、练习与解答的现状

### 2. 对每个 patch KP，决定主稿插入策略

按以下决策树：

```
patch KP 与主稿哪个小节最紧密关联？
├─ 完全延伸某小节的话题 → 在该小节末尾追加一段（无需新建小节）
├─ 引入一个独立子机制/分支 → 在父小节下新建子小节（如 7.2.1）
├─ 引入与主线并列的新主题（罕见） → 新建小节（如 7.6）
└─ 仅是某机制的额外例题/方法 → 进入"例题讲解"或"常见误区"段
```

**插入点要自然**：找一个原章节读起来"该展开但当时没展开"的位置。新内容应该让那个位置感觉"本来就该有"。

### 3. 调整周边结构（如需）

允许的微调：
- 重写过渡句让前后衔接自然
- 把原本的某段拆/合以容纳新内容
- 调整小节标题措辞（不改 anchor 时谨慎；改 anchor 见下文）
- 在覆盖记录里加新 KP id
- 在关键术语里加新术语
- 在练习与解答里加新题

**禁止**：
- 改章节标题
- 删除现有内容（如果新 KP 推翻了某个已有结论 —— 这是违反单调积累原则的，应在 rebalance 阶段就 hold）
- 在正文写"补充"、"新增"等元语言
- 在小节名加 `*` 或 `(new)` 等标记

### 4. 稳定 anchor 维护（如果引用密集）

如果项目里跨章引用频繁，考虑给新建小节加显式 anchor：

```markdown
### 7.2.1 多级页表的查找代价 {#ch07-pagetable-cost}
```

后续 ch08 引用时用 `[多级页表的查找代价](ch07-storage-foundations.md#ch07-pagetable-cost)`。

如果项目里跨章引用很少，不必加 anchor。

### 5. 生成 supplement 文档

每个 patch KP 一份 `book/supplements/chMM-<kp-slug>.md`。文件名建议英文 slug。

模板：

```markdown
# chMM 补充：<知识点中文名>

本次补充对应主稿位置：第 M 章「<相关小节中文名>」之后/之内的 X.Y.Z 节。

## 新增知识点

- <要点 1>
- <要点 2>
- <要点 3>

## 与原章节的连接

<2-4 句散文，说明这个知识点为什么属于这一章；它解决了原章节哪个被搁置或省略的具体问题；以及它和后续章节的桥接。>

## 自测

1. <问题 1（来自 KP 的 retrieval_hooks 或新生成）>
   **解答要点**：<...>

2. <问题 2>
   **解答要点**：<...>

(2-3 题足够，每题就近给答案。)

## 建议已读者

<一句话引导>：如果你已经读过第 M 章，**只需补读第 M 章 X.Y.Z 节，并回看「<相关小节>」末段**，并尝试本文自测。
```

**注意**：
- 文件名 / 标题 / 内容**全部不写日期、不写版本、不写"本次"以外的时间标记**。
- 标题用知识点名（中文 OK），不用 `update-N` 这种命名。
- supplement 读起来像"一直就在那"的深入材料，不像更新日志。

### 6. 状态翻转

对每个 patch KP：
- `status: queued → applied`
- `reader_notice: needed → published`
- 删除 `action` 字段
- 保留 `applied_to`、`detail_cards`、`links`

### 7. open-questions 联动

如果 patch 内容回答了某 OQ → 标 `状态: closed`、`关闭于: chMM`、`关闭 KP: <id>`、移到"已解决"段。

### 8. Cleanup

删除 `.in-progress.yaml`。Run checks:

```bash
python3 scripts/check_kp_schema.py <project-root>
python3 scripts/check_chapter_frontmatter.py book/chMM-*.md
python3 scripts/check_open_questions.py <project-root>
```

### 9. 报告给用户

```
已补 ch07-storage-foundations:
  - 主稿吸收 2 个 KP: 多级页表代价, 地址翻译深层细节
  - 微调了 7.2 节末尾过渡句以引出新内容
  - 专题文档:
    - book/supplements/ch07-multilevel-pagetable-cost.md
    - book/supplements/ch07-addr-translation-deep.md
  - reader_notice → published

已读过 ch07 的读者，只需读上述两份 supplement 即可同步最新内容。
```

## Write Boundaries

- ✅ `book/chMM-slug.md`（目标章，可微调结构）
- ✅ `book/supplements/chMM-<kp-slug>.md`
- ✅ `assets/figures/chMM-*.svg`（若新 KP 需要图）
- ✅ `spec/knowledge-points.yaml`（status / reader_notice / action 字段翻转）
- ✅ `spec/open-questions.md`
- ❌ 其他章节文件
- ❌ source-index, terminology, style-guide, chapter-template
- ❌ course-skeleton（patch 不改章节状态）

## 多 KP 同章合并写 vs 拆分写

如果一次 Stage D 要把 3+ 个 KP 补到同一章：
- 主稿里**一次性集中插入**（避免反复修改打乱 git 历史与可读性）
- 每个 KP 仍**独立生成一份 supplement**（一个 KP 一份是规则）
- 如果 3 个 KP 是同一概念簇，可以考虑只生成一份 supplement 涵盖整个簇 —— 但要在 audit 中说明这么做的理由。默认 1 KP = 1 supplement。

## Don't

- 不要在主稿里加任何"新增"、"补充"、"v2" 等元语言或时间戳。
- 不要在 supplement 里写日期、版本、"本次更新"。
- 不要替换原章节段落 —— 单调积累原则禁止覆盖已有结论。
- 不要在 Stage D 里写新章节（那是 Stage C）。
- 不要在 Stage D 里改 course-skeleton 的章节状态（patch 不算"重写"）。
- 不要为了 supplement 看起来丰富而硬塞与该 KP 无关的内容。
