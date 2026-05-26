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

视觉强调是注意力预算。先选层级，再写文字。

### 视觉强调层级

| 标记 | 语义 | 用途 | 不用于 |
|---|---|---|---|
| 普通正文 | 默认阅读流 | 因果、解释、过渡 | 需要扫读定位的结构 |
| `**加粗**` | 术语锚点 | 概念首次出现、被定义的术语、callout 标题 | 整句判断、句中关键词角色 |
| `<u>下划线</u>` | 轻量注意 | 已知术语在句中需要被注意的条件、限制、对照点 | exam_tip 消费、长句、连续多处 |
| `==高亮==` | 强记忆信号 | 必考判断、易混辨析、核心结论、必背并列项 | 普通定义、背景解释 |
| Callout | 停顿/辨析 | 核心判断、易错点、常见误区、思维停顿 | 装饰性总结 |
| 图/表/公式/步骤 | 结构承载 | 流程、比较、状态、分类、层次、变量关系 | 用文字强调替代结构 |

`**` 与 `<u>` 的分界：`**` 标的是被引入/被定义的术语本身；`<u>` 标的是已知术语在当前句中扮演的角色（条件、限制、对照点）。当一个词同时是"首次术语"和"句中关键角色"时，优先用 `**` 引入，把角色交给上下文散文。

### 检查清单

- [ ] `==...==` 只包判断核，不包整段定义；不连续多段高亮。
- [ ] `<u>...</u>` 只包短条件、短限制、短关键词；不替代 exam_tip 消费。
- [ ] `**...**` 只用于概念首次出现、被定义的术语、callout 标题。
- [ ] 同一分句内不堆多个标记；需要并存时拆句。
- [ ] 流程、比较、分类、状态、变量关系交给图/表/公式/步骤，不用强调标记硬撑。
- [ ] callout 必须帮助辨析、判断或迁移，不为过检查而塞。

### 例子

Bad — 整段定义被升成高亮：

```markdown
==操作系统是一组控制和管理计算机硬件与软件资源的软件。==
```

Bad — 同一分句内同时堆 `**` 和 `==`：

```markdown
**操作系统**负责管理资源，==并发不等于并行==。
```

Good — 高亮只包判断核：

```markdown
复用包括 ==时分复用和空分复用==。
```

Good — 下划线给句中关键词角色：

```markdown
分时系统关心的是 <u>交互响应时间</u>，而不是单纯提高吞吐量。
```

Good — 术语首次引入用加粗，判断核拆到下一句再用高亮：

```markdown
**操作系统**负责管理硬件与软件资源。一个常见辨析是：==并发不等于并行==。
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
