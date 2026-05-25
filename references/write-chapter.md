# Reference: Stage C — Write Chapter

Trigger: `inspect_state.py` reports `kp_status.queued_new` non-empty AND one or more chapters have all their queued KPs ready. Or user says "写第 N 章 / 生成 chXX".

> **Stage C 的座右铭：成书。** 写出的章节要让读者感觉是一本"已经打磨完成的书"的某一章，不出现任何工作流术语。诚实承认本章无法深入的内容，但用自然散文表达。

## Input

- `spec/knowledge-points.yaml`（特别是 `action: new_chapter` + `applied_to: <target>` 的 KP）
- `spec/chapter-template.md`
- `spec/style-guide.md`
- `spec/terminology.md`
- `spec/course-skeleton.md`（看上一章 introduces / continues）
- 上一章 `book/ch(N-1)-*.md` 的 front-matter（生成"上章回顾"用）

## Output

- `book/chNN-slug.md` —— 主稿，包含 front-matter 与正文
- KP 状态翻转：`status: queued → applied`，清掉 `action` 字段
- `spec/course-skeleton.md` —— 本章状态从 `drafted-pending` 改为 `drafted`
- `spec/open-questions.md` —— 登记本章产生的新 OQ；勾选闭合的 OQ

**Do NOT touch**: source-index, terminology, style-guide, chapter-template, 任何其他章的文件。

## In-Progress Marker

```yaml
stage: write-chapter
batch: 003
target: ch08-memory-management
kp_ids:
  - OSPPT-CH08-PAGE-TABLE
  - OSPPT-CH08-MULTILEVEL-PT
  - ...
notes: "Stage C drafting ch08 from rebalance-003 output"
```

Recovery:
- If `book/ch08-*.md` exists with substantial content → ask user 续写 or 重写
- If file empty or absent → 从 template 重启

## Naming

文件名：`chNN-slug.md`，slug 用短英文 kebab-case（如 `ch08-memory-management`）。
- NN 是教科书章节号，由 Stage B 决定（不一定等于原 PPT 的章节号）。
- slug 简洁、英文、kebab-case，用于跨章引用稳定。

## Process

### 1. Read inputs

读 target 章节的所有 queued KP（按 cognitive_role 分类）：
- `foundation` —— 开篇问题与核心抽象的根据
- `mechanism` —— 主线展开的骨架
- `method` —— 具体步骤/技术
- `example` —— 例题素材
- `formula` —— 公式、定量关系
- `pitfall` —— 常见误区
- `exam_pattern` —— 考试出题模式

读 detail_cards（按 type）：
- `method/example/operation/figure/exam_tip` —— 决定它们出现在正文哪里（主线、例题、常见误区、figure embed）

### 2. 决定叙事顺序

骨架建议（不绝对）：

```
foundation 引入 → mechanism 展开 → method/operation 具体化 → example 验证 → formula/exam_pattern 提炼 → pitfall 收尾
```

但**主线由概念逻辑决定，不由 role 序号决定**。如果某个 example 比 mechanism 更适合做开篇钩子，就放前面。

### 3. 应用模板

读 `spec/chapter-template.md`，按结构生成：

```markdown
---
chapter: ch08-memory-management
title: <章节标题>
assumes:                # 上游章节已 introduce 的概念 id
  - ch07-introduces:文件存储抽象
  - ch07-introduces:磁盘 I/O 模型
introduces:             # 本章新引入的概念
  - 多级页表
  - TLB 与 page fault 协作
  - ...
continues:              # 由本章承接但不深入的概念
  - 虚拟内存替换算法
open_questions:         # 本章登记的 OQ
  - OQ-004
coverage:               # 本章覆盖的 KP id
  - OSPPT-CH08-PAGE-TABLE
  - ...
---

# 第 8 章：<标题>

## 学习目标

(3-5 条具体目标，从 KP 的 concept 摘要得出)

## 上章回顾

(三条以内，激活前置知识。从 ch(N-1).introduces 取 3 条，**用一句话散文重写**，不是机械列点。)

## 开篇问题

(一个反直觉的、具体的问题/现象，由 foundation 类 KP 启发。**不允许定义开头**。)

## 本章地图

(一段自然散文，说明本章要解决什么；其中可以包含"本章先关注 X，至于 Y，要等到我们引入 Z 之后才能讲清楚"这样的边界说明 —— 但**不允许**用 "defer/future-unknown/TODO" 等词。)

## 正文

(按"痛点 → 机制 → 例子 → 代价/边界"展开。每个核心 KP 至少有一个对应小节。)

### 8.1 <小节名>

...

### 8.2 <小节名>

...

> **思维停顿**：(一个具体的概念问题，就近回答。1-2 次/章。)

## 例题讲解

(来自 detail_cards.type=example 的内容，给出完整解题过程。)

## 常见误区

(来自 detail_cards.type=exam_tip 的内容 + role=pitfall 的 KP，每条简洁说明并给出辨析。)

## 本章小结

(3-5 句话，复述驱动问题及本章答案。)

## 关键术语

(每条独立段落格式：`**中文术语（English term）** 一句话解释。`)

## 练习与解答

(2-5 题，每题就近给答案/解题路径。优先用 detail_cards 里的考题。)

## 覆盖记录

(列出本章覆盖的 KP id。机器可读，但放在章末不打扰读者阅读节奏。)
```

### 4. 散文化诚实

**禁止**在正文出现以下措辞：
- `defer`、`future-unknown`、`TODO`、`待补充`
- "本章无法回答"、"留给后续章节"（作为单独标题）
- "(将在第 X 章中讲解)" 这类括号注释如果章号尚未确定

**允许**的散文表达模式：
- "我们这里先把 X 理解为 Y；至于 X 在并发场景下的更完整含义，等学了同步原语之后回头看会更自然些。"
- "本章只关注 A 视角的 B；C 视角的同样问题会在引入 D 工具后变得清晰。"
- "完整的算法分析需要 E 概念支撑，我们先用一个直观的例子建立感觉。"

### 5. 使用 detail_cards

写正文与例题时**主动消费** detail_cards：
- `figure` 卡 → 在正文该位置生成对应 SVG（命名 `assets/figures/ch08-<concept>.svg`），用 Markdown 图片引用。
- `example` 卡 → 进入"例题讲解"段。
- `method` 卡 → 进入正文相应小节作为具体步骤说明。
- `operation` 卡 → 工程师视角侧栏（可选）或正文具体步骤。
- `exam_tip` 卡 → 优先进"常见误区"段。

不允许把 detail_cards 整张吞掉而不用。如果某张卡确实不适合本章，**显式标记**到 KP 上：`detail_cards[i].deferred: true`，待 Stage D 或后续章节再用。

### 6. 桥接 retrieval_hooks

为每个核心 KP，**补充** `retrieval_hooks.bridging`：
- 与前章某 KP 对比的迁移题
- 引用本章后续小节的预测题
- 跨章应用题

这些会出现在练习区或本章/邻章的回顾段中。

### 7. 关闭和登记 open questions

读 `spec/open-questions.md`：
- 如果本章 KP 回答了某条 open OQ → 在 OQ 条目下标 `状态: closed`、`关闭于: ch08`、`关闭 KP: <id>`、移到"已解决"段。
- 如果本章引出了无法当章回答的问题（"我们这里先按 X 处理；完整故事在 Y 之后") → 登记新 OQ，并在 front-matter `open_questions` 添加 id。

### 8. 状态翻转

对本章所有 queued KP：
- `status: queued → applied`
- 删除 `action` 字段
- 保留 `applied_to`、`reader_notice`、`links`、`detail_cards`

### 9. 更新 course-skeleton

把本章状态从 `drafted-pending` 改为 `drafted`：

```markdown
## 章节

- ch01-introduction — 待写
- ch07-storage-foundations — drafted
- ch08-memory-management — drafted   ← 新增/更新
```

### 10. Cleanup

Delete `.in-progress.yaml`. Run checks:

```bash
python3 scripts/check_kp_schema.py <project-root>
python3 scripts/check_chapter_frontmatter.py book/ch08-*.md
python3 scripts/check_open_questions.py <project-root>
```

### 11. 报告

```
已生成 ch08-memory-management 草稿 (book/ch08-memory-management.md):
  - 覆盖 KP: 6 个
  - 引入概念: 多级页表, TLB 协作, ...
  - 新 OQ: 1 条 (OQ-005)
  - 关闭 OQ: 1 条 (OQ-002)
  
按你的设计，我已经在草稿正文里用自然散文交代了"完整虚拟内存替换算法在后续章节展开"。

下一步? (pool / queued_patch 状态见 inspect_state)
```

## Write Boundaries

- ✅ `book/chNN-slug.md`（目标章）
- ✅ `assets/figures/chNN-*.svg`（本章新增 figures）
- ✅ `spec/knowledge-points.yaml`（**仅** status / action 字段翻转，以及 `retrieval_hooks.bridging` 补充）
- ✅ `spec/course-skeleton.md`（本章状态）
- ✅ `spec/open-questions.md`
- ❌ 其他章节文件
- ❌ supplements
- ❌ source-index, terminology, style-guide, chapter-template

## Don't

- 不要在正文写 "TODO / defer / 后续补充" 等工作流痕迹。
- 不要在正文加日期或版本号。
- 不要写到读者真的无法读懂 —— 如果某个概念本章一定要用但**没**前置 KP 支撑，**回 Stage B 看是否要 patch 前章**，而不是在本章硬塞解释。
- 不要主动改 chapter-template.md 或 style-guide.md。它们是项目共享 spec。
- 不要在 Stage C 同时写两章 —— 一次只写一章，写完报告后由用户决定是否继续下一章。
