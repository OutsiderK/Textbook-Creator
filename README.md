# online-course-textbook

A Claude/Codex skill for building a textbook from an ongoing course's incremental PPT/PDF releases. The skill handles the full pipeline (ingest → rebalance → write → patch → optional lab) through internal state-driven routing — the user speaks naturally and the skill judges the next stage.

> **核心约束**：
> - 主稿读起来像"已经打磨完成的书"，不留工作流术语。
> - 内部追溯/审计/状态机完整可见。
> - 主稿持续演进，补充文档只服务已读读者；不写日期或版本。
> - 章节切分按概念聚簇，数量规则只做软提醒。

## What's in here

```
online-course-textbook/
├── SKILL.md                              # 路由器 + 行为规则（propose/override/recovery）
├── references/                           # progressive disclosure, load on demand
│   ├── initialize.md                     # Stage Init
│   ├── ingest.md                         # Stage A
│   ├── rebalance.md                      # Stage B
│   ├── write-chapter.md                  # Stage C
│   ├── patch-chapter.md                  # Stage D
│   ├── lab-policy-and-design.md          # Lab module
│   └── quality-checks.md                 # Check 脚本运行表
├── scripts/                              # 确定性脚本
│   ├── inspect_state.py                  # 状态路由器入口
│   ├── check_kp_schema.py                # hard
│   ├── check_chapter_frontmatter.py      # hard
│   ├── check_open_questions.py           # soft
│   └── check_lab.py                      # hard (code labs), soft (observation)
└── assets/templates/                     # init 阶段拷入项目的初始文件
    ├── knowledge-points.yaml
    ├── chapter-template.md
    ├── style-guide.md
    ├── lab-policy.yaml
    ├── terminology.md
    ├── course-skeleton.md
    └── open-questions.md
```

## Install

按"实体目录放 codex 端，Claude 端做软链"的约定：

```bash
# 1. 把实体目录搬到 codex 端
mv /home/coder/workspace/Work/UTC/online-course-textbook ~/.codex/skills/online-course-textbook

# 2. Claude 端建软链
ln -s ~/.codex/skills/online-course-textbook ~/.claude/skills/online-course-textbook

# 3. 验证
ls -la ~/.claude/skills/online-course-textbook
```

或直接保留在 `Work/UTC/` 下开发，软链两端都过来：

```bash
ln -s /home/coder/workspace/Work/UTC/online-course-textbook ~/.codex/skills/online-course-textbook
ln -s /home/coder/workspace/Work/UTC/online-course-textbook ~/.claude/skills/online-course-textbook
```

## Dependencies

- Python 3.8+
- PyYAML：`pip install pyyaml`

## User-facing entry points

skill 被 Codex/Claude 在以下场景自动加载：

| User says | Skill behavior |
|---|---|
| "初始化这门 X 教材" | Init only |
| "把这份 PPT 加进教材" | Inspect + propose Stage A |
| "摄入 ch08.pdf" | Override mode: Stage A only on ch08.pdf |
| "继续更新教材" / "根据最新 PPT 更新课本" | Auto mode: propose next stage per priority |
| "写第 8 章" | Override mode: Stage C only on ch08 |
| "把第 7 章补完整" | Override mode: Stage D only on ch07 |
| "检查状态" | Run all checks; report |
| "设计实验" | Lab module |

**核心行为**（详见 `SKILL.md`）：
- **Propose, don't execute**：每次先报告状态，等用户确认。不自动链式执行多 stage。
- **Override**：用户给具体目标（PPT 名 / 章号），只做指定动作。完成后**不**自动进入下一 stage。
- **Recovery**：检测到 `spec/.in-progress.yaml` 时，先问"继续 / 丢弃 / 取消"。

## Project Layout (the skill operates on)

```
<project-root>/
├── inputs/                       # 用户把 PPT 放这里
├── spec/
│   ├── source-index.yaml         # PPT registry (dedup 用)
│   ├── knowledge-points.yaml     # 知识全集
│   ├── course-skeleton.md        # 当前目录与章节状态
│   ├── open-questions.md         # 跨章追踪
│   ├── terminology.md
│   ├── style-guide.md
│   ├── chapter-template.md
│   ├── lab-policy.yaml           # 仅 enabled 时存在
│   └── .in-progress.yaml         # 仅 stage 进行中时存在
├── book/
│   ├── chXX-slug.md              # 主稿
│   └── supplements/
│       └── chXX-kp-name.md       # 知识点专题（无日期、无版本）
├── labs/                         # 仅 lab enabled 时存在
│   └── labXX-slug/
├── assets/figures/               # SVG 等图表
└── docs/
    ├── ingest-NNN.md             # 摄入审计（数字 batch id，不用日期）
    └── rebalance-NNN.md          # 重平衡审计（仅非平凡决策）
```

## Six principles (in every stage)

1. **单调积累** — 已有知识点不推翻
2. **内外分层** — 内部追溯/审计；读者文本自然/连贯
3. **主稿演进** — 主稿吸收新知识，supplement 是给已读读者的通知
4. **延迟归属** — 不确定 KP 留 pool
5. **聚簇切分** — 章节边界由概念关联度决定
6. **应试细节保留** — PPT 中的方法/技巧/例题/图表抓进 `detail_cards`

## Stage outputs at a glance

| Stage | KP status flow | Files touched |
|---|---|---|
| Init | (none) | spec/* (init), book/, docs/, inputs/ (dirs) |
| A. Ingest | (new) → pool | knowledge-points.yaml (append), source-index.yaml, docs/ingest-NNN.md |
| B. Rebalance | pool → queued (+action+reader_notice) | knowledge-points.yaml (status fields), course-skeleton.md, open-questions.md, docs/rebalance-NNN.md (非平凡时) |
| C. Write | queued (new_chapter) → applied | book/chXX-*.md, knowledge-points.yaml (status flip), course-skeleton.md, open-questions.md |
| D. Patch | queued (patch_chapter) → applied (reader_notice → published) | book/chMM-*.md (修改), book/supplements/chMM-*.md, knowledge-points.yaml, open-questions.md |
| Lab | — | labs/labXX-*/* |

## Smoke test the scripts

```bash
# Empty project should suggest initialize
mkdir /tmp/test-project && python3 scripts/inspect_state.py /tmp/test-project

# Initialized empty project should pass checks
mkdir -p /tmp/test-project/spec
cp assets/templates/knowledge-points.yaml /tmp/test-project/spec/
cp assets/templates/open-questions.md /tmp/test-project/spec/
echo 'sources: []' > /tmp/test-project/spec/source-index.yaml
echo 'next_batch_id: 1' >> /tmp/test-project/spec/source-index.yaml
python3 scripts/check_kp_schema.py /tmp/test-project       # ✓
python3 scripts/check_open_questions.py /tmp/test-project  # ✓
```

## Forbidden patterns (auto-checked)

`check_chapter_frontmatter.py` flags these tokens in any `book/*.md`:

- `defer`、`future-unknown`、`TODO`、`待补充`
- `⚡新增`、`本次更新`、`本次新增`
- `(将在第 X 章中讲解)` 类括号注释
- 版本号 `vN.M`
- 日期 `YYYY-MM-DD` 在 supplement 里也禁止

诚实承认未深入要用自然散文。

## When this skill should NOT fire

- 用户问"如何写一本教材" → 这是策略问题，不要触发 skill。
- 用户问 Claude API、Anthropic SDK 用法 → 不相关。
- 用户在一个非 textbook 项目里工作 → 不触发。
- 用户的输入既没有 PPT 也没有要求处理教材 → 不触发。

## License / Ownership

私人项目使用。
