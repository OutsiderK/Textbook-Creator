# Reference: Stage B — Rebalance

Trigger: `inspect_state.py --json` reports `knowledge_points.status_counts.pool > 0`, or user says "重平衡 / 做 rebalance / 看看现在能写哪些".

> **Stage B 的座右铭：定形。** 这是**唯一**做章节级决策的阶段。它不写正文。它的输出是"谁进哪章"+"哪些走 patch"+"哪些先 hold"。

## Input

- `spec/knowledge-points.yaml`（特别是 `status: pool` 的 KP）
- `spec/course-skeleton.md`（已有章节状态）
- `spec/open-questions.md`（看是否能闭合）
- 已写的 `book/chXX-*.md`（看 patch 候选）

## Output

每个被处理的 pool KP **必须**得到一个明确归属，通过 yaml 直接编辑写入 KP 的 `status` + `queue.*`：

| 归属 | KP 字段设置 |
|---|---|
| 进入新章 | `status: queued`, `queue: {action: new_chapter, target: book/chNN-slug.md, batch: <id>}`, `reader_notice: none` |
| 补入已有章 | `status: queued`, `queue: {action: patch_chapter, target: book/chMM-slug.md, batch: <id>}`, `reader_notice: needed` |
| 暂留 (hold) | `status: queued`, `queue: {action: hold, reason: <enum>, batch: <id>}`, `reader_notice: none` |

附加输出：

- `spec/course-skeleton.md`——新增章节标 `status: drafted-pending`；patch 候选章节不动状态。
- `spec/open-questions.md`——关闭被本批 KP 回答的 OQ；登记本次 cluster 产生的新 OQ。
- `docs/rebalance-<batch>.md`——仅在**非平凡**决策时生成（拆/合/补旧章/突破数量规则）。简单决策（一批 KP 干净进一个新章）不必写。

**Do NOT touch**: `book/chXX.md`、`book/supplements/`、`source-index.yaml`。

## Interruption Safety

Stage B does not use `workflow_job.py`. It is a single atomic yaml rewrite (knowledge-points.yaml + course-skeleton.md + open-questions.md).

- If interrupted before the KP yaml is written → no state change; just re-run.
- If interrupted after KP yaml is written but before course-skeleton/open-questions are updated → re-run; the queued KPs are idempotent.

## The Seven Questions

For each candidate cluster of KPs, walk through these in order. Document non-trivial answers in `docs/rebalance-<batch>.md`.

### Q1 — 这些 KP 是否形成一个自然主题簇？

判据：
- 共享一个核心抽象（例：同步问题与管程都是"协调访问共享资源"）
- 共享一个共同问题（例：进程模型/PCB/进程控制都是"操作系统怎么把进程当成对象管理"）
- 共享一个机制族（例：FCFS/SJF/SRTN/HRRN/RR 都是非抢占/抢占调度算法）

如果是 → 候选成簇；否则 → 看能否拆出多簇。

### Q2 — 主题簇内部有没有共同问题、机制或例题线索？

簇内 KP 应该能用一个连续叙事讲完：痛点 → 机制 → 例子 → 代价/边界。

如果簇里 KP 跳跃太大（一个是 foundation，一个是 exam_pattern，中间没有 mechanism 桥接），就不是一章——可能要等更多 KP 来补，或者拆。

### Q3 — 放成一章是否会认知负荷过高？

数量护栏（软）：
- 核心 KP（`core: true`）数量 5–9 通常合适。
- 超过 9 → 检查是否拆。
- 少于 5 → 检查是否合并、作为某章小节、或继续 hold。
- 如果簇极紧密、不可拆，**允许突破数量上限**（如 11–12），但需在 audit 写突破理由。
- 如果是算法/机制重型 KP（如调度算法、页面替换算法），即使少于 5 个核心 KP 也可独立成章。

### Q4 — 拆开后是否会割裂理解链条？

判据：
- 拆开后两边都不完整？保持合一。
- 拆开后各自有完整故事？可以拆。
- 拆出来的小章节后续会接（同源后续 PPT 会补全）？可以拆，但标 `status: drafted-thin` 提示。

### Q5 — 是否有 KP 更适合补入旧章？

如果某个 KP 的 `links.prerequisites` 全在某已写章里，且不构成新主题 → patch 该旧章。
如果某个 KP 的 `links.extends` 指向某已写章的 KP → patch。
如果原 PPT 的反向引用早期内容暗示某旧章 → patch。

Patch 候选的 KP 不进新章簇。

### Q6 — 是否有 PPT 细节应进入例题/方法/常见误区，而不是正文主线？

这是关于 detail_cards 的使用，不影响 KP 的章节归属。做好标记即可（不必单独建状态）。Stage C/D 会读 detail_cards 决定放主线还是 sidebar/exercise。

### Q7 — 是否有 open question 被回答？

读 `spec/open-questions.md` 的 `当前 open` 段。对每条：
- 本批 KP 是否提供了回答？
- 若是，在 OQ 条目下标 `状态: closed`、`关闭于: chNN`（即将分配该 KP 的章节）、`关闭 KP: <kp-id>`。
- 移动到 `已解决` 区段。

## 数量规则与连贯性的优先级

> **数量规则负责提醒，知识连贯性负责决定。**

数量超阈值是**触发再判断**，不是**强制拆分**。如果你判定簇必须保持紧密，写一句 audit："因为 X 与 Y 通过共同同步原语紧耦合，11 个核心 KP 仍作为单章。"

## hold 的合法理由 (queue.reason)

只在 `queue.action: hold` 时填写。可选值（schema 强制）：

- `awaiting_followup` — 等后续 PPT 把同主题补完整
- `bridging_undefined` — 该 KP 跨多个潜在章节，需要看到更多关联 KP 才能定
- `enrichment_only` — 该 KP 本身是某个未来章的扩展材料，主章节核心还没出现
- `manual_review` — 复杂度足够高，建议用户提示后再分配

**禁止的理由**：

- "懒得判断"
- "可能以后会用"
- "应该重要但说不上来"

如果 KP 在 hold 状态超过 2 个 batch 而没动 → **强制在 audit 里讨论**，提示用户："`OSPPT-CH08-MMF` 已 hold 3 批，reason: enrichment_only。是否手动指定归属？"

## 状态变更与字段表

写入 yaml 时（直接编辑 spec/knowledge-points.yaml）：

| 簇决策 | 每个 KP 设置 |
|---|---|
| 形成新章 chNN | `status: queued`, `queue: {action: new_chapter, target: book/chNN-slug.md, batch: <id>}`, `reader_notice: none` |
| 补入已有章 chMM | `status: queued`, `queue: {action: patch_chapter, target: book/chMM-slug.md, batch: <id>}`, `reader_notice: needed` |
| 暂留 hold | `status: queued`, `queue: {action: hold, reason: <enum>, batch: <id>}`, `reader_notice: none` |

**重要**：rebalance 直接写 yaml；不要调 `workflow_job.py start`。`workflow_job` 是 Stage C/D 进入正文修改前的锁，rebalance 还没到那一步。

## 章节切分的实战建议

参考既有教材切分：
- **进程模型、PCB 与进程控制**（fork/vfork/exec/exit/sleep + 状态转换 + 上下文）——因为这些都围绕"进程作为操作系统对象的生命周期"。
- **经典同步问题与管程**（生产者-消费者 + 哲学家 + 读者-写者 + 管程）——因为这些都是"用同步原语解决具体协作模式"的具体应用。
- **中断与内核边界**（外部中断 + 异常 + 自陷 + 用户/内核态转换）——因为这些围绕"用户代码与内核代码的边界穿越机制"。

每章一个**驱动问题** + 一个**核心机制族**。这是聚簇判断的内核。

## Cleanup

Run `python3 scripts/check_kp_schema.py` (hard) and `python3 scripts/check_open_questions.py` (soft).

## 报告给用户

```
重平衡 batch 003 完成：
  新章建议: ch08-memory-management (5 个 KP, queue.action=new_chapter)
  补入旧章: ch07-storage-foundations (2 个 KP, queue.action=patch_chapter, reader_notice=needed)
  暂留 hold: 1 个 KP (OSPPT-CH08-MMF, queue.reason: bridging_undefined)
  关闭 OQ: 1 条 (OQ-002 关闭于 ch08)

非平凡决策详见 docs/rebalance-003.md。

下一步可选 (按 inspect_state.py 提示):
  1. 进入 Stage C 写 ch08 草稿
  2. 进入 Stage D 把 2 个 KP 补到 ch07

按 SKILL.md 规则，我会等你确认后再继续。
```

**Do NOT auto-trigger Stage C/D.**

## Don't

- 不要为了"看起来产物多"而把暂留 KP 强行分章——hold + reason 是合法状态。
- 不要把 KP 从 pool 直接跳到 applied——必须经过 queued。
- 不要用日期作为 batch id（与 `source-index.yaml.next_batch_id` 对齐用数字）。
- 不要修改 KP 的 `source`、`detail_cards`、`role`、`links` 等 Stage A 设定的内容。
- 不要在 rebalance 里写 `book/`，那是 Stage C/D 的事。
- 不要在 rebalance 里调 `workflow_job.py`——那是 Stage C/D 用的写作锁。
