# Style Guide

This file is the project-local presentation checklist. Treat checklist items as rules for Stage C unless the chapter context clearly requires a documented exception in `spec/visual-plans/<stem>.yaml`.

## 写章节时必须做

- [ ] 用自然散文解释因果、边界和权衡；不要把正文写成 bullet dump。
- [ ] 有 `visual_reviewed: true`、`type: figure` 或 `must_cover` 的 card，必须在 visual plan 中有呈现决策。
- [ ] `must_cover` 必须进入 visual plan 声明的载体；普通正文覆盖只在 `representation: [prose]` 且有 `reason` 时成立。
- [ ] `exam_tip` 的核心断言必须用 `==...==`、callout 或练习/答案消费。
- [ ] 公式必须配相邻变量说明表。
- [ ] 比较、分类、状态、流程、架构优先使用表格、步骤、状态表或 SVG。
- [ ] 图表和 callout 就近放在第一次需要它的位置。
- [ ] 每个图前后至少有一句说明它解决什么阅读问题。
- [ ] 章节读起来像成书，不暴露工作流、更新痕迹或内部状态词。

## 强调

- [ ] `==...==` 只用于 `exam_tip`、必考并列项、关键判别和易混判断。
- [ ] `**...**` 只用于概念首次出现、关键术语、关键断言和 callout 标题。
- [ ] 不整段高亮，不连续多段高亮，不用高亮标普通定义。
- [ ] 不为了过检查塞空洞 callout；callout 必须帮助辨析、判断或迁移。

Bad:

```markdown
==复用是操作系统的基本特征==。
```

Good:

```markdown
复用包括 ==时分复用和空分复用==。
```

## 图表

- [ ] 图负责保留结构：流程、架构、状态、层次、复杂关系。
- [ ] 表负责比较、分类、变量解释和判别清单。
- [ ] 公式块负责定量关系，变量表负责符号含义与条件。
- [ ] 步骤表或有序列表负责顺序，不把 3 步以上流程吞进长段落。
- [ ] 多个视觉 card 可以合并，但 visual plan 必须写 `group` 和 `reason`。
- [ ] 不强制每张 figure card 单独生成 SVG；强制的是结构化呈现或有理由的 prose。

## Callout

Use these labels exactly so checks and readers can recognize them:

```markdown
> **核心判断**：...
```

```markdown
> **易错点**：...
```

```markdown
> **常见误区**：...
```

```markdown
> **思维停顿**：...
```

## 公式

Formula block:

```markdown
$$
CPU\ Utilization = 1 - p^n
$$
```

Adjacent variable table:

```markdown
| 符号 | 含义 |
|---|---|
| `p` | 单道程序等待 I/O 的时间比例 |
| `n` | 内存中的程序道数 |
```

## 概念对照表

```markdown
| 概念 | 关注点 | 常见误区 |
|---|---|---|
| 并发 | 同一时间间隔内推进 | 不等于同一时刻同时执行 |
| 并行 | 同一时刻同时执行 | 是并发的更严格情形 |
```

## Forbidden Tokens

These tokens must not appear in reader-facing `book/**/*.md` prose:

- `defer`, `future-unknown`, `future_unknown`
- `TODO`, `FIXME`, `XXX`
- `pool`, `queued`, `rebalance`, `workflow`
- `待补充`, `待完善`, `待定`
- `新增`, `本次新增`, `本次补充`, `本次更新`
- `v1`, `v2`, `v1.0`, version markers such as `2026-`, `2025-`
- speculative notes such as `(将在第 X 章中讲解)` when X is not a real chapter id

## Natural Boundary Language

Use boundary language as part of the reader's learning path:

- "我们这里先把 X 理解为 Y；至于 X 在并发场景下的更完整含义，等学了同步原语之后回头看会更自然些。"
- "本章只关注 A 视角的 B；C 视角的同样问题会在引入 D 工具后变得清晰。"
- "完整的算法分析需要 E 概念支撑，我们先用一个直观的例子建立感觉。"
