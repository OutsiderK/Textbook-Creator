# Reference: Stage A — Ingest

Trigger: `inspect_state.py --json` reports unindexed source files under `sources/ppts/`. Or the user explicitly says "摄入 X.pdf".

> **Stage A 的座右铭：保真。** 这一阶段不写章节、不改目录、不做章节归属判断。只做 KP 提取、细节卡片提取、与已有账本去重和连接。

## Input

- One PPT/PDF file from `sources/ppts/`.
- Existing `spec/knowledge-points.yaml` (may be empty).
- Existing `spec/source-index.yaml`.
- Existing `spec/terminology.md` (for term consistency).

## Output

- `spec/knowledge-points.yaml` — new KPs appended (status=pool, no queue field) + existing KPs' sources/detail_cards augmented.
- `spec/source-index.yaml` — this PPT recorded with its batch id.
- `docs/ingest-<batch>.md` — audit report.

**Do NOT touch**: `course-skeleton.md`, `open-questions.md`, any `book/` files.

## Batch ID

Use `spec/source-index.yaml`'s `next_batch_id`, then increment it. Format batch as zero-padded 3-digit: `001`, `002`, etc. Files use that suffix: `docs/ingest-001.md`.

If the user ingests multiple PPTs in one user turn (override mode), each PPT gets its own batch id and audit file. Do them sequentially.

## Interruption Safety

Stage A does not use `workflow_job.py`. It is a yaml-append-only operation:

- `source-index.yaml` is updated atomically (single rewrite).
- `knowledge-points.yaml` is updated atomically (single rewrite).
- `docs/ingest-<batch>.md` is created last.

If interrupted mid-stage:
- If `source-index.yaml` entry exists for this PPT but no audit file → roll back the source-index entry and re-run.
- If audit file exists → ingest considered complete.

## Process

### 1. Read the PPT (text skeleton + targeted visual notes)

一份 PPT 通常 30–80 张幻灯片；整本视觉读会烧 50K–100K token。Stage A v2 的正确做法是**先建立逐页文本骨架，再把必要视觉信息转成 `visual_page_notes`，最后用 text + notes 一起提取 KP**。视觉信息不是 KP 提取后的补丁。

**1.1 — pdfplumber text skeleton scan**

通过 Bash 工具运行并保存输出到 `tmp/page-review/batch-<batch>/text.json` 和 `tmp/page-review/batch-<batch>/text.txt`：

```python
import json
from pathlib import Path
import pdfplumber

pdf_path = Path("sources/ppts/<file>.pdf")
out_dir = Path("tmp/page-review/batch-<batch>")
out_dir.mkdir(parents=True, exist_ok=True)

records = []
with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages, start=1):
        text = page.extract_text() or ""
        records.append({
            "page": i,
            "text": text,
            "chars": len(text),
            "images_raw_count": len(page.images),
            "tables_raw_count": len(page.find_tables()),
        })

(out_dir / "text.json").write_text(
    json.dumps(records, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
(out_dir / "text.txt").write_text(
    "\n\n".join(f"=== Slide {r['page']} ===\n{r['text']}" for r in records),
    encoding="utf-8",
)
```

这一步只建立骨架，不做最终视觉风险判定，不要求全页 contact sheet，也不要求逐页 `thumbnail_observation`。

如果环境没 pdfplumber：`pip install pdfplumber`（也是 `/pdf` skill 推荐的栈）。退化方案用 `pypdf` 也行，但 pdfplumber 的页级元信息更有用。若没有 Poppler 命令，但有 PyMuPDF/fitz 和 Pillow，可用 PyMuPDF 渲染目标页作为视觉复核输入。

**1.2 — Teaching image prepass**

对当前 PDF 运行 `$find-teaching-image-slides`，让它负责“严格教学图片页”的召回和去模板噪声：

```bash
python3 /home/coder/.codex/skills/find-teaching-image-slides/scripts/scan_teaching_image_pages.py \
  sources/ppts/<file>.pdf \
  --out tmp/page-review/batch-<batch>/teaching-image-scan
```

然后按该 skill 的流程查看 `teaching_image_pages.md`、`contact_*.jpg`，填写 `review_decisions_template.csv`，并运行：

```bash
python3 /home/coder/.codex/skills/find-teaching-image-slides/scripts/finalize_review_decisions.py \
  tmp/page-review/batch-<batch>/teaching-image-scan/teaching_image_pages.json \
  tmp/page-review/batch-<batch>/teaching-image-scan/review_decisions_template.csv
```

Stage A 必须把 `confirmed + uncertain` 加入最终视觉复核集合。不要把 `$find-teaching-image-slides` 当作全部判定器：它识别教学图片页，但不能覆盖“没有教学图片、却因文本抽取乱序而无法理解”的页。

**1.3 — Build visual_page_notes before KP extraction**

对 teaching-image `confirmed + uncertain` 的每页，先渲染单页 PNG，再生成 `visual_page_notes`。可以使用项目模板脚本：

```bash
python3 scripts/render_stage_a_pages.py \
  sources/ppts/<file>.pdf \
  --pages 37,48,50 \
  --out tmp/page-review/batch-<batch>/pages
```

`visual_page_notes` 是正式 KP 提取的输入，必须把视觉知识转成结构化文本；不要只写“有图”或“已复核”。

```yaml
visual_page_notes:
  - page: 37
    source: teaching_image
    rendered_page: tmp/page-review/batch-002/pages/p037.png
    visual_observation: 页面中央是有界缓冲区示意图，包含生产者、消费者、缓冲区、输入/输出方向。
    provisional_concepts:
      - 有界缓冲区中的生产者-消费者关系
    must_capture:
      - 生产者向缓冲区放入产品。
      - 消费者从缓冲区取出产品。
      - 缓冲区容量有限，因此需要同步与互斥。
    possible_detail_card_type: figure
    confidence: high
```

字段要求：

- `page`：1-indexed 页码。
- `source`：`teaching_image` 或 `comprehension_blocker`。
- `blocker`：仅 `source: comprehension_blocker` 时必填。
- `rendered_page`：渲染出的图片路径。
- `visual_observation`：视觉上看到了什么。
- `provisional_concepts`：图或版面中可能对应的概念候选。
- `must_capture`：进入教材时不能丢失的节点、步骤、关系、变量、条件、行列、箭头方向等。
- `possible_detail_card_type`：建议类型，如 `figure`、`method`、`operation`、`exam_tip`。
- `confidence`：`high | medium | uncertain`。

**1.4 — Joint text + visual note KP extraction**

正式提取 KP 时，输入流必须按页组织：

```text
Slide N:
  extracted_text: ...
  visual_page_notes: ...  # 如果有
```

当某页有 `visual_page_notes`，必须把 notes 与抽取文本同等看待。允许跨相邻页聚合成同一个 KP；图片页中只出现在图里的知识点也可以创建 KP 或 `detail_cards`。

**1.5 — Inline comprehension blocker handling**

每处理到一页或一个页段，都做这个自检：

```text
如果我把这页写成 KP/detail_card，是否有任何关键结构是我只能猜、不能从当前文本可靠确认的？
```

如果答案是“是”，该页就是 `comprehension_blocker`。立即暂停该页的 KP 判断，渲染页面，生成 `source: comprehension_blocker` 的 `visual_page_notes`，注入当前页输入，然后继续提取。不要把 blocker 留到最后，因为它们可能包含独立 KP。

典型 blocker：

- 代码/伪代码页：无法确定执行顺序、缩进层级、分支归属、循环范围、P/V 调用位置。
- 表格页：无法确定行列对应关系、比较维度、表头归属。
- 公式/推导页：无法确定公式结构、上下标、变量绑定、推导顺序。
- 流程/步骤页：无法确定先后顺序、条件分支、箭头方向。
- 案例/例题页：无法确定题干、条件、步骤、结论之间的对应关系。
- 抽取文本明显交错、重复、断裂、跨栏混排，agent 只能“猜”原始页面。

**1.6 — Page-risk audit schema**

Stage A v2 推荐写 `docs/page-risk-<batch>.yaml`，`schema_version: 2`。所有页仍要有 `page_risks`，但只有进入最终视觉复核集合的页必须有 `visual_page_notes`。

```yaml
schema_version: 2
summary:
  pdf: sources/ppts/<file>.pdf
  pages_total: 116
  teaching_image_count: 2
  comprehension_blocker_count: 1
  final_visual_review_count: 3

text_skeleton:
  path_json: tmp/page-review/batch-002/text.json
  path_txt: tmp/page-review/batch-002/text.txt

teaching_image_scan:
  tool: find-teaching-image-slides
  scan_dir: tmp/page-review/batch-002/teaching-image-scan
  json: tmp/page-review/batch-002/teaching-image-scan/teaching_image_pages.json
  decision_ledger: tmp/page-review/batch-002/teaching-image-scan/review_decisions_template.csv
  confirmed: [37, 50]
  uncertain: []
  excluded:
    - page: 1
      reason: template/title decoration only

visual_page_notes:
  - page: 48
    source: comprehension_blocker
    blocker: extracted_text_reading_order_corrupt
    rendered_page: tmp/page-review/batch-002/pages/p048.png
    visual_observation: 页面为两列售票问题伪代码，左列给出进程循环和进入互斥区，右列给出 if/else 分支。
    provisional_concepts:
      - 用记录型信号量解决售票问题
    must_capture:
      - 每个进程按旅客要求找到 A[j] 后执行 P(mutex)，进入互斥区。
      - 读取 Xi := A[j] 后判断 Xi >= 1。
      - 有票时 Xi 减一并写回 A[j]，随后 V(mutex)，再输出一张票。
      - 无票时先 V(mutex)，再提示票已售完，并 goto L1。
    possible_detail_card_type: method
    confidence: high

final_visual_review_pages:
  - page: 37
    source: teaching_image
    risk_level: high
    page_class: process_diagram
  - page: 48
    source: comprehension_blocker
    risk_level: high
    page_class: code_or_command

page_risks:
  - page: 1
    risk_level: low
    page_class: normal_text
    evidence: [text_sufficient]
  - page: 37
    risk_level: high
    page_class: process_diagram
    evidence: [teaching_image]
    visual_note_ref: 37
  - page: 48
    risk_level: high
    page_class: code_or_command
    evidence: [extracted_text_reading_order_corrupt]
    visual_note_ref: 48
```

`schema_version` 缺失时按 v1 旧审计处理，以兼容历史项目。

**1.7 — Sanity spot-check**

随机抽 2–3 张（标题页 + 1–2 张中段）用当前可用的视觉路径读一遍，校验 KP 提取是否反映幻灯实际内容。这一步是质量抽样，不是主视觉发现机制。它主要抓：

- pdfplumber 返回空（纯图片 slide）
- 内容顺序判错
- 视觉强调（如 ==考点==、红框、加粗箭头）在纯文本里丢了

如果 spot-check 发现明显丢失，优先生成相关页的 `visual_page_notes`，然后重新检查受影响 KP/detail_cards。

### 2. Extract KPs

Per concept identified in the PPT:

- Decide if it's a **new concept** or an **enhancement of an existing KP**:
  - Compare against existing KPs by `concept` (semantic match, not just string).
  - Same concept under different wording → augment existing KP.
  - Genuinely new → create new KP.

For each new KP, fill:

```yaml
- id: <SOURCE-CHNN-SLUG>      # e.g. OSPPT-CH08-PAGE-TABLE
  concept: 简短中文描述
  source:
    - ppt: 第八章存储管理.pdf
      slides: [12, 13, 14]
  core: true                  # foundational/mechanism → true; example/exam-only → false
  role: foundation            # foundation|mechanism|method|example|formula|pitfall|exam_pattern
  status: pool                # fresh ingest: no queue field yet
  applied_to: []
  reader_notice: none
  detail_cards: []            # filled in step 3
  links:
    prerequisites: []
    extends: []
    contrasts: []
  retrieval_hooks:
    local:                    # 1-3 self-contained quiz prompts
      - "..."
    bridging: []              # filled in Stage C when neighbors known
```

**注意**：fresh ingest KP **不写 `queue` 字段**。`queue` 只在 Stage B 决定归属时由 rebalance 写入。

**ID convention**: `<SOURCE>-CH<NN>-<SLUG>`. `SOURCE` is the PPT family tag (e.g., `OSPPT` for the course's PPT series). `CH<NN>` is the source PPT's chapter number (the original course chapter, not our target textbook chapter). `SLUG` is a short concept tag.

### 3. Extract detail_cards

For each KP, scan the source slides for usable details. Each card looks like:

```yaml
- type: method              # method|example|operation|figure|exam_tip
  summary: 一句话概括
  source_slide: 14
  deferred: false           # default; flip to true if Stage C/D decides not to use
```

Categories:

- **method**: a procedure or technique (e.g., "用二分思想分析页表深度")
- **example**: a worked-out instance from the PPT (e.g., "课件给出的进程调度甘特图实例")
- **operation**: a concrete step or command (e.g., "strace -e write 观察 system call")
- **figure**: a diagram or table worth reproducing (e.g., "FAT12 磁盘结构图")
- **exam_tip**: a likely exam pattern or trap (e.g., "考试常考 ==饿死== vs ==死锁== 区别")

**保真原则**：尽量保留 PPT 中的应试细节。宁可多抓一张 card，写正文时再选用，不要因为"看着不重要"就扔掉。Stage C 和 D 会按需消费。

For visually reviewed high-risk pages, use richer cards when the visual carries required details:

```yaml
- type: figure
  summary: 引导过程图展示从上电到用户空间的控制转移。
  source_slide: 18
  visual_reviewed: true
  review_risk_level: high
  page_class: process_diagram
  structure_kind: ordered_chain   # ordered_chain|comparison|state_machine|formula|taxonomy|process|case_steps|table|diagram
  verified_items:
    - Master Boot Record
    - Stage 1 bootloader
    - GRUB
  must_cover:
    - item: Master Boot Record
      aliases: [MBR, 主引导记录]
      role: node
    - item: Stage 1 bootloader
      aliases: [一级引导程序]
      role: node
    - item: GRUB
      aliases: [Grand Unified Bootloader]
      role: implementation
```

`must_cover` is cross-disciplinary. Use `item`, not `term`, because required details may be formulas, variables, steps, conditions, categories, rows/columns, case facts, or named entities.

Use `must_cover` only for details that should survive into the textbook. Do not make every visible label mandatory. Prefer items that are exam-relevant, structurally necessary, or needed to understand a process/table/formula/case.

Two defer levels are distinct:

- `detail_cards[].deferred: true` means the whole card is not used in the current chapter.
- `detail_cards[].must_cover[].deferred: true` means the card is used, but that specific item is intentionally not expanded; add `defer_reason`.

Examples of `structure_kind` extraction focus:

- `ordered_chain` / `process`: nodes, sequence, arrows, branch conditions.
- `comparison` / `table`: compared objects, dimensions, key differences.
- `state_machine`: states and transition conditions.
- `formula`: formula, variables, assumptions, derivation result.
- `taxonomy`: hierarchy and category boundaries.
- `case_steps`: facts, steps, decision points, conclusion.

### 4. Augment existing KPs

If a KP from this PPT matches an existing KP:

- Append the new `source` entry (don't replace).
- Append new `detail_cards`.
- Do NOT change `status`, `core`, `role`, `applied_to`, `links` — those belong to other stages.

### 5. Set `links` (best-effort)

While extracting, note relationships:

- A KP that obviously builds on another → `prerequisites`.
- A KP that generalizes another → `extends`.
- A KP that contrasts with another → `contrasts`.

Don't agonize over completeness; Stage B will refine.

### 6. Generate local `retrieval_hooks`

For each new KP, write 1–3 local quiz prompts. They should be answerable from this KP's content alone (no cross-chapter knowledge required at this stage).

### 7. Update source-index

```yaml
sources:
  - path: sources/ppts/第八章存储管理.pdf
    file: 第八章存储管理.pdf
    batch_id: 003
    ingested_kps: [OSPPT-CH08-PAGE-TABLE, ...]
    augmented_kps: [OSPDF-C04-VIRTUAL-MEMORY, ...]
    slides_count: 79
next_batch_id: 4
```

The `path` field (project-relative) is required so `inspect_state.py` can recognize the source as indexed; `file` (basename) is retained for human readability.

### 8. Write audit report

`docs/ingest-003.md`:

```markdown
# Ingest Batch 003: 第八章存储管理.pdf

- PPT slides: 79
- New KPs: <count>
- Augmented KPs: <count>

## New KPs

| ID | concept | role | core | slides |
|---|---|---|---|---|
| OSPPT-CH08-PAGE-TABLE | 多级页表 | mechanism | true | 12-14 |
| ... | | | | |

## Augmented KPs

| ID | new sources / detail_cards |
|---|---|
| OSPDF-C04-VIRTUAL-MEMORY | +source slides 8-11; +detail_card (figure: 虚拟到物理地址映射图) |

## Detail cards captured (highlights)

- (method) 多级页表查找的递归过程 → OSPPT-CH08-PAGE-TABLE, slide 13
- (figure) 二级页表查找示意 → slide 14
- (exam_tip) 常考 ==TLB miss + page fault== 双重开销 → slide 18
- ...

## 可能影响旧章的内容

(列出本批 KP 中可能反向补到已有章节的：通过 prerequisites / extends 对已有 applied KP 的引用判断)

- 本批 OSPPT-CH08-TLB-DETAILS 与已写的 ch07 提到的"地址翻译"相关，**Stage B 可能判定为 patch ch07**。

## 尚不能判断归属的 KP

- OSPPT-CH08-MEMORY-MAPPING：与 ch11 虚存和 ch14 文件系统都有关，由 Stage B 决定。
```

### 9. Cleanup

Run these checks — both must pass:

```bash
python3 scripts/check_kp_schema.py
python3 scripts/check_page_risk.py docs/page-risk-<batch>.yaml
```

## Report to User

> 已摄入 `<file>`：新增 KP `<n>` 个，增强已有 KP `<m>` 个，写入 detail cards `<k>` 张。审计见 `docs/ingest-003.md`。
> （Pool 现有 `<pool-count>` 个 KP；按 `inspect_state.py` 的下一步建议是 Stage B 重平衡，等你确认。）

**Do NOT auto-trigger Stage B.** Every stage transition needs propose-confirm.

## Don't

- 不要在 ingest 阶段给 KP 添加 `queue` 字段。`queue` 是 Stage B 的产物。
- 不要在 ingest 阶段写 `book/` 任何文件。
- 不要扔掉看似"次要"的细节——应试细节宁多勿少。
- 不要把同一个 PPT ingest 两遍——source-index 是 dedup 依据。如果用户明确说"重新摄入"，先 roll back 旧记录再做。
