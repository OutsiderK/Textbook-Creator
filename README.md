# online-course-textbook

一个 Claude / Codex skill：把一门**正在进行、PPT 逐周发布**的课程，增量地构建成一本读起来像成书的教材。整条流水线（摄入 → 重平衡 → 写章 → 补充 → 可选实验）由 `scripts/inspect_state.py` 做**状态驱动路由**——用户用自然语言说话，skill 自己判断该走哪一阶段。

> **四条核心约束**
> - 主稿读起来像"已经打磨完成的书"，不留任何工作流术语。
> - 内部追溯 / 审计 / 状态机完整可见（外人看不到，维护者全看得到）。
> - 主稿持续演进，补充文档只服务"已读过旧版"的读者；不写日期、不写版本。
> - 章节切分按概念聚簇，数量规则只做软提醒。

这个 README 面向**维护者**。模型实际执行时读的是 [SKILL.md](SKILL.md)（路由器 + 行为规则）和按需加载的 `references/`。

---

## What's in here

```
online-course-textbook/
├── SKILL.md                          # 路由器 + 行为规则（propose / override / recovery）
├── README.md                         # 本文件（维护者视角）
├── references/                       # progressive disclosure，按阶段单独加载
│   ├── initialize.md                 # Init
│   ├── ingest.md                     # Stage A 摄入
│   ├── rebalance.md                  # Stage B 重平衡
│   ├── write-chapter.md              # Stage C 写章
│   ├── integrate-supplement.md       # Stage D 补充（patch 旧章 + 写 supplement）
│   ├── lab-policy-and-design.md      # Lab 模块
│   └── quality-checks.md             # check 脚本 → 严重度 → 何时跑
└── assets/project-template/          # init 时整包拷入新项目的脚手架
    ├── spec/                         # knowledge-points / source-index / workflow-state /
    │                                 # course-skeleton / open-questions / terminology /
    │                                 # style-guide / chapter-template / reference-chapter /
    │                                 # quality-overrides / lab-policy / lab-template / visual-plans/
    ├── scripts/                      # inspect_state / workflow_job / check_* / render_stage_a_pages / common
    ├── book/supplements/
    ├── assets/figures/
    ├── sources/ppts/                 # 用户把 PPT/PDF 放这里
    ├── labs/
    └── docs/reference-chapter-annotation.md
```

> 注意：reference 文件名是 `integrate-supplement.md`（不是 `patch-chapter.md`）；脚手架目录是 `assets/project-template/`（不是 `assets/templates/`）。

---

## 工作流与状态模型

五个阶段 + 一个可选 Lab 模块。阶段之间**从不自动链式触发**——每完成一步都 re-inspect 并 propose 下一步，等用户确认。

```
Init → Stage A 摄入 → Stage B 重平衡 → Stage C 写新章
                          └────────────→ Stage D 补旧章 + 写 supplement
                    （任意时刻可触发 Lab 模块 / quality checks）
```

整个内容状态收敛在 `spec/knowledge-points.yaml` 的 KP（knowledge point）账本里。每个 KP 有两个正交维度：

**`status`**（单一来源的内容状态）

| status | 含义 |
|---|---|
| `pool` | 已摄入但未分配。**没有 `queue` 字段。** |
| `queued` | Stage B 已决定去向，带 `queue.action`：`new_chapter` / `patch_chapter` / `hold`（hold 必带 `queue.reason` 枚举）。 |
| `applied` | 已写入主稿。`queue` 清空，`applied_to: [book/chNN-…]` 记录归属（list，支持一 KP 多章）。 |

**`reader_notice`**（独立维度，给已读读者的通知状态）：`none` → `needed`（Stage B 标 patch）→ `published`（Stage D 完成）。

状态翻转有纪律：Stage A/B **直接编辑 yaml**（幂等、可重跑）；Stage C/D **只能经 `workflow_job.py`** 翻转 `status` / `queue` / `applied_to` / `reader_notice` / 锁字段。这层非对称是有意的——见下文 Recovery。

---

## Install

约定：**实体目录放 Codex 端，Claude 端做软链**（与本机其它 skill 一致）。

```bash
# 实体目录在 ~/.codex/skills/online-course-textbook
# Claude 端建软链指向它
ln -s ~/.codex/skills/online-course-textbook ~/.claude/skills/online-course-textbook

# 验证两端都能看到
ls -la ~/.claude/skills/online-course-textbook
```

若在别处开发，两端都软链过来即可。

## Dependencies

| 库 | 用途 | 必需性 |
|---|---|---|
| Python 3.8+（开发于 3.11） | 运行全部脚本 | 必需 |
| **PyYAML** (`yaml`) | 几乎所有脚本读写 spec yaml | 必需 |
| **markdown-it-py** (`markdown_it`) | `check_visual_assets` / `check_chapter_presentation` 解析 Markdown；**无 regex 退化**，缺失即报错 | Stage C 检查必需 |
| **pdfplumber** | Stage A 建立逐页文本骨架（`references/ingest.md`） | Stage A 需要（退化：`pypdf`） |
| **PyMuPDF** (`fitz`) | `render_stage_a_pages.py` 渲染待视觉复核的页 | Stage A 视觉复核需要 |
| Pillow + Poppler | 备选渲染路径 | 可选 |
| `$find-teaching-image-slides` skill | Stage A 教学图片页召回与去模板噪声 | Stage A 推荐；缺失时退化为人工抽样视觉复核 |

```bash
pip install pyyaml markdown-it-py pdfplumber pymupdf
```

`xml.etree`（SVG `<text>` 解析）是标准库，无需安装。

---

## 初始化一个新项目

```bash
# 在目标项目根目录执行（trailing /. 表示拷贝内容而非目录本身）
cp -r ~/.codex/skills/online-course-textbook/assets/project-template/. <project-root>/
cd <project-root>
python3 scripts/inspect_state.py --json   # 全新空项目：actions 为 []（或仅 ingest，若已放入 PPT）
python3 scripts/check_kp_schema.py         # ✓
```

实际由 skill 走 Init 阶段（见 [references/initialize.md](references/initialize.md)）：确认课程名/语言/lab 政策，拷模板，按课程定制 `terminology.md`、`course-skeleton.md`、`lab-policy.yaml`——**不预填章节大纲**（那是 PPT 来了之后 rebalance 才决定的）。

---

## User-facing entry points

skill 在以下场景被自动加载并路由：

| 用户说 | skill 行为 |
|---|---|
| "初始化这门 X 教材" | Init only |
| "把这份 PPT 加进教材" | inspect + propose Stage A |
| "摄入 ch08.pdf" / "只摄入这份" | Override：仅对 ch08.pdf 跑 Stage A |
| "继续更新教材" / "根据最新 PPT 更新" | Auto：按 `inspect_state.py` 优先级 propose 下一阶段 |
| "写第 8 章" / "生成 ch08" | Override：仅对 ch08 跑 Stage C |
| "把第 7 章补完整" / "补充第 7 章" | Override：仅对 ch07 跑 Stage D |
| "重平衡" / "做 rebalance" | Stage B only |
| "检查状态" / "跑 check" | 跑 quality checks 并报告 |
| "设计实验" / "给 chXX 加个 lab" | Lab 模块 |

**三条核心行为**（详见 [SKILL.md](SKILL.md)）：

- **Propose, don't execute**：`requires_proposal: true` 或用户说得含糊时，先报告状态、propose 下一步、等确认；不自动链式跑多阶段。
- **Override**：用户给了具体目标（PPT 名 / 章号 / 阶段名），只做指定动作；完成后 re-inspect 并报告新状态，**不**自动进入下一阶段。
- **Recovery**：`inspect_state.py` 报告 `workflow.interrupted: true`（存在 `spec/workflow-state.yaml.current_job` 或有被锁 KP）时，先问"继续 / 丢弃 / 取消"，再动半成品文件。丢弃用 `python3 scripts/workflow_job.py abort`。

---

## Project Layout（skill 操作的项目结构）

```
<project-root>/
├── sources/ppts/                  # 用户把 PPT/PDF 放这里（也识别 PPTs/ 等目录）
├── spec/
│   ├── source-index.yaml          # PPT 登记表（dedup 依据）+ next_batch_id
│   ├── knowledge-points.yaml      # KP 账本（内容状态的单一来源）
│   ├── workflow-state.yaml        # current_job 锁 + history（Stage C/D 用）
│   ├── course-skeleton.md         # 演进中的目录 + 章节状态
│   ├── open-questions.md          # 跨章追踪
│   ├── visual-plans/
│   │   └── chNN-slug.yaml          # 每章的图文呈现契约（Stage C 产出）
│   ├── quality-overrides.yaml     # 列出免检的 legacy 章（无 visual-plan 的历史章）
│   ├── terminology.md
│   ├── style-guide.md             # 写作规则 + 禁词清单
│   ├── chapter-template.md
│   ├── reference-chapter.md       # 图文密度与组件的范例章
│   └── lab-policy.yaml            # enabled: true | false | undecided
├── book/
│   ├── chNN-slug.md               # 主稿章节
│   └── supplements/
│       └── chMM-<kp-slug>.md      # 知识点专题（无日期、无版本）
├── assets/figures/
│   └── chNN-*.svg                 # 章节图表
├── labs/                          # 仅 lab enabled 时存在
│   └── labXX-slug/
└── docs/
    ├── ingest-NNN.md              # 摄入审计（数字 batch id，零填充 3 位）
    ├── page-risk-NNN.yaml         # Stage A 页级风险审计（可选，schema v2）
    └── rebalance-NNN.md           # 重平衡审计（仅非平凡决策）
```

> `spec/workflow-state.yaml` 是 Stage C/D 的事务锁（旧设计里的 `.in-progress.yaml` 已废弃）。中断恢复完全由它的 `current_job` 字段驱动。

---

## 七条原则（每个阶段都适用）

1. **单调积累** — 已有知识点不推翻，只扩展、连接、细化。
2. **内外分层** — 内部追溯/审计/状态机；读者文本自然/连贯/像成书。
3. **主稿演进** — 主稿吸收新知识，不在正文留更新痕迹；supplement 是给已读读者的通知，不是第二正文。
4. **延迟归属** — 不确定的 KP 留 `hold`（`queue.action: hold` + `queue.reason`），不硬塞章节。
5. **聚簇切分** — 章节边界由概念关联度决定；数量规则只做软提醒。
6. **应试细节保留** — PPT 里的方法/技巧/例题/图表/易错点抓进 KP 的 `detail_cards`。
7. **视觉保真** — 对纯文本抽取可能丢失的图/表/公式/流程/状态图/代码截图/扫描页做风险分级；默认只视觉复核 `high` 页。

---

## Stage outputs at a glance

| Stage | KP 状态流转 | 主要落盘文件 |
|---|---|---|
| **Init** | （无） | `spec/*`（拷模板）；建 `book/ docs/ sources/ppts/ labs/ assets/figures/` |
| **A 摄入** | （新建）→ `pool`（无 queue） | `knowledge-points.yaml`（append）、`source-index.yaml`、`docs/ingest-NNN.md`、可选 `docs/page-risk-NNN.yaml` |
| **B 重平衡** | `pool` → `queued`（+`queue.action`+`reader_notice`） | `knowledge-points.yaml`（状态字段）、`course-skeleton.md`、`open-questions.md`、`docs/rebalance-NNN.md`（非平凡时） |
| **C 写章** | `queued(new_chapter)` → `applied` | `book/chNN-*.md`、`assets/figures/chNN-*.svg`、`spec/visual-plans/<stem>.yaml`、`course-skeleton.md`、`open-questions.md`；状态翻转经 `workflow_job.py finish` |
| **D 补充** | `queued(patch_chapter)` → `applied`，`reader_notice: needed → published` | `book/chMM-*.md`（修改）、`book/supplements/chMM-*.md`、`assets/figures/chMM-*.svg`、`open-questions.md`；状态翻转经 `workflow_job.py finish --reader-notice published` |
| **Lab** | （无） | `labs/labXX-*/*`、`spec/lab-policy.yaml`（仅 init / 切换 enabled 时） |

每个阶段只能改它的 reference 声明的文件（见 SKILL.md "Write Boundaries"）；要动共享 spec（`terminology.md` / `style-guide.md` / `chapter-template.md`）必须先问用户。

---

## Quality checks（脚本 → 严重度）

完整映射见 [references/quality-checks.md](references/quality-checks.md)。`hard` 失败阻断阶段；`soft` 仅警告。

| 脚本 | 何时跑 | 严重度 | 校验什么 |
|---|---|---|---|
| `inspect_state.py [--json]` | 每次开工 + 每阶段后 | 状态报告 | 项目状态与下一步建议（路由 SSOT） |
| `check_kp_schema.py` | A/B/C/D、init | hard | KP schema、status/queue 规则、卡片字段 |
| `check_page_risk.py docs/page-risk-NNN.yaml` | A | hard | Stage A 页级风险审计（兼容 v1 contact-sheet 与 v2 visual_page_notes） |
| `check_chapter_frontmatter.py` | C/D | hard + soft | front matter 结构（hard）+ 读者正文工作流术语泄漏（soft） |
| `check_detail_coverage.py [chapter]` | C/D | hard | `must_cover` 是否落进正文/图/表/supplement，除非 deferred |
| `check_visual_assets.py [chapter]` | C | hard | visual plan 存在；声明的输出与正文/资产匹配；结构载体覆盖 `must_cover` |
| `check_chapter_presentation.py [chapter]` | C | hard + soft | 公式邻接变量表、`exam_tip` 消费（hard）；强调/段落节奏（soft） |
| `check_open_questions.py` | B/C/D | soft | open-question 结构与交叉引用 |
| `check_lab.py labs/labXX/` | Lab 后 | hard（code lab）/ soft（observation） | lab 文件齐备、verify 可跑 |

**Stage C 首选入口**：`python3 scripts/workflow_job.py validate book/chNN-slug.md`——跑与 finish 相同的硬检查路径，但不需要活动 job。

逃生口：`STAGE_C_HARD_CHECKS=warn` 可把 Stage C 的 finish 闸门降级为非阻断；`spec/quality-overrides.yaml` 的 `legacy_chapters` 让历史章跳过 presentation/visual 检查（`inspect_state.py` 会报告这笔技术债）。

---

## 读者正文里的禁忌（写作规则 vs 自动检查）

**写作规则**（写 Stage C/D 时人为遵守，SSOT 在 `spec/style-guide.md` 与 `references/write-chapter.md`）——读者正文与 supplement 禁止出现：

- 工作流术语：`defer`、`future-unknown`、`TODO`、`待补充`、`pool`、`queued`、`rebalance`
- 更新元语言：`新增`、`本次新增`、`本次更新`、`⚡新增`
- 时间/版本标记：日期 `YYYY-MM-DD`、版本号 `vN.M`（supplement 里同样禁止）
- 投机性章节引用：`(将在第 X 章中讲解)` 当 X 还不是真实章节 id

无法深入的内容要用**自然散文**承认，而不是留工作流痕迹。

**自动兜底**：`check_chapter_frontmatter.py` 只覆盖上面的一个**子集**，不要把它当成全部保障——

- *hard error*：缺 YAML front matter；缺必填键 `{id, title, order, coverage}`；章节 `id` 重复。
- *soft warning*：正文含 `future unknown / defer / pool / rebalance / queued / workflow`（大小写不敏感子串）；或命中 `新增…20xx` / `20xx…补充` 的日期式更新语。

> 即：禁词清单里的 `TODO / 待补充 / 本次新增 / vN.M / (将在第X章)` **不被该脚本拦截**，靠写作纪律保证。

---

## Smoke test

```bash
cd ~/.codex/skills/online-course-textbook

# 1) 用脚手架拉起一个临时项目
rm -rf /tmp/oct-smoke && mkdir -p /tmp/oct-smoke
cp -r assets/project-template/. /tmp/oct-smoke/

# 2) 在该项目里跑（脚本从自身位置解析 ROOT=parents[1]，必须在项目内运行，不接路径参数）
cd /tmp/oct-smoke
python3 scripts/inspect_state.py --json     # 全新项目：actions []，requires_proposal false
python3 scripts/check_kp_schema.py           # ✓ 0 errors
python3 scripts/check_open_questions.py      # ✓（soft）
```

> `inspect_state.py` **不接受位置参数**；它从脚本自身路径推导项目根。要测某个项目，把脚本随模板拷进去后在该项目目录里运行。

---

## When this skill should NOT fire

- 用户问"如何写一本教材" → 策略问题，不触发。
- 用户问 Claude API / Anthropic SDK 用法 → 不相关。
- 用户在一个非 textbook 项目里工作 → 不触发。
- 输入既没有 PPT、也没有处理教材的诉求 → 不触发。

---

## License / Ownership

私人项目使用。
