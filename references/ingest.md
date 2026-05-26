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

### 1. Read the PPT (hybrid: text-first, risk-ranked visual)

一份 PPT 通常 30–80 张幻灯片；整本视觉读会烧 50K–100K token。正确做法是**先用 pdfplumber 抓文本，再对图表页做风险排序后的视觉补全**。视觉补全使用当前环境可用的路径：能直接读取 PDF 页面就直接读；不能直接读时，先把目标页渲染成 PNG 再视觉复核。

**1.1 — pdfplumber 骨架扫描（一次拿全文本 + 准确页号）**

通过 Bash 工具运行：

```python
import pdfplumber
with pdfplumber.open("sources/ppts/<file>.pdf") as pdf:
    for i, page in enumerate(pdf.pages, start=1):
        text = page.extract_text() or ""
        has_images = bool(page.images)
        marker = "  [has images]" if has_images else ""
        print(f"=== Slide {i}{marker} ===")
        print(text)
```

这一步搞定 **~80% 的 KP 提取**，并为视觉复核做页面审计：

- 每个 KP 的 `concept`、`role` 判定
- `detail_cards.type` ∈ {method, operation, exam_tip} 的 summary
- `source.slides` 字段的精确填写
- 标记好每页的文本长度、图片/表格/公式/代码/图示迹象，供 1.2 风险分级用

如果环境没 pdfplumber：`pip install pdfplumber`（也是 `/pdf` skill 推荐的栈）。退化方案用 `pypdf` 也行，但 pdfplumber 的 page.images 检测更准。若没有 Poppler 命令（如 `pdftoppm`、`pdfinfo`、`pdfimages`），但有 PyMuPDF/fitz 和 Pillow，可用 PyMuPDF 渲染单页或 contact sheet 作为视觉复核输入。

**1.2 — 页面风险分级：输出视觉复核队列**

对每页做跨学科风险判断。不要只依赖中文关键词；结合结构信号、英文标题、抽取异常和相邻页上下文。

先渲染覆盖**所有页面**的低分辨率缩略图/contact sheet，并逐页判断是否存在非模板视觉内容。每张 contact sheet 最多包含 20 页。缩略图用于分类，不用于抽取图中文字细节；它必须帮助识别大块嵌入图片、流程框、箭头、表格、公式、代码/截图块、图表或结构图。

注意 PPT 母版背景、装饰图、页脚 logo 和重复模板元素会污染 `page.images` 信号：图片数量或面积只能作为候选证据，不能单独决定 high。用 contact sheet 区分真正承载知识的流程图、表格、公式、截图与纯装饰背景。

结构信号：

- 低文本或空文本，但页面有可见内容。
- 大图、多图、截图、扫描页、矢量框图、箭头、图表、曲线、表格、代码/命令块。
- 公式/推导文本疑似乱序，或表格行列关系可能丢失。
- 标题页/过渡页字体很大但内容很少；只有确认页面没有实质性的非模板图块、流程框、箭头、表格、公式、代码/截图或结构图时，才可标为 `section_divider`。

中英文词汇信号：

- 中文：过程、流程、步骤、阶段、链路、机制、算法、模型、结构、架构、层次、组件、状态、转换、示意、对比、比较、分类、公式、推导、定理、证明、例题、案例、实验、装置、表。
- English: process, procedure, workflow, pipeline, lifecycle, phase, stage, sequence, mechanism, algorithm, model, architecture, structure, hierarchy, framework, component, stack, layer, state, transition, diagram, comparison, compare, versus, vs, taxonomy, classification, formula, equation, derivation, theorem, proof, case, example, experiment, lab, table.

给每页分配：

- `risk_level`: `high | medium | low | section_divider`
- `page_class`: `process_diagram | architecture_diagram | state_machine | comparison_table | formula_derivation | chart_or_plot | code_or_command | case_steps | taxonomy | table | screenshot_or_scanned | section_divider | text_dense | normal_text`

默认策略：

- `high` 页必须视觉复核。
- `medium` 页默认不视觉复核；只有用户要求、抽查 medium 后发现漏点、或 high 页复核显示相邻 medium 页明显相关时，才升级复核。
- 若页面抽取文本很少，但缩略图显示非模板大图块、流程框、箭头、表格、公式、代码/截图、图表或结构图，不能直接降级为 `section_divider` 或 `low`。必须先单页渲染做分类复核：只判断该视觉是否承载知识结构。确认承载知识结构则标为 `high`；确认只是装饰或无教学信息，才可降级，并在审计中记录反证。
- `section_divider` 页只作为上下文，不单独视觉复核；但它必须已经通过缩略图和必要的单页分类复核确认没有实质图表/流程/公式/表格/截图。

如果项目已有合适脚本，可写 `docs/page-risk-<batch>.yaml`。没有脚本时，也要在 `docs/ingest-<batch>.md` 写出同等信息：

```yaml
summary:
  pdf: sources/ppts/<file>.pdf
  pages_total: 79
  high_count: 5
  medium_count: 9
  section_divider_count: 4
review_queue:
  - page: 18
    priority: 1
    risk_level: high
    page_class: process_diagram
    evidence: [low_text, large_image, keyword_process]
    why_visual_needed: 纯文本只保留标题，流程节点和箭头方向在图中。
    expected_extraction_focus:
      - 节点、顺序、箭头方向、分支条件
      - 图中具名实体和缩写
false_positive_control:
  section_dividers:
    - page: 17
      reason: 章节/小节过渡页，只为后续页提供上下文。
      demotion_evidence:
        text_only_title: true
        non_template_visual: false
        structural_marks: []
  uncertain_sample:
    - page: 42
      reason: medium 风险表格页，若 high 页发现表格抽取丢行列关系再复核。
```

**1.3 — 只对 high 页做视觉补全**

对 `review_queue` 中 `risk_level: high` 的页使用视觉读取，捕捉纯文本抓不到的：

- 流程图：节点、顺序、箭头方向、分支条件。
- 架构图：组件、层级、连接关系。
- 状态图：状态、转换条件。
- 表格/对照表：行列标题、比较维度、关键差异。
- 公式推导：公式、变量、适用条件、推导结论。
- 图表曲线：坐标轴、变量、趋势、拐点、结论。
- 代码/命令：命令、参数、输出、执行顺序。
- 案例/例题：步骤、已知条件、解题路径、结论。

调用方式取决于当前工具环境。若有 PDF-native 视觉读取工具，精确读取 high 页范围；若没有，使用可用渲染器先把 high 页转成 PNG 再读取。可用的本地 fallback 是 PyMuPDF/fitz：

```python
from pathlib import Path
import fitz

pdf_path = Path("sources/ppts/<file>.pdf")
out_dir = Path("tmp/page-review")
out_dir.mkdir(parents=True, exist_ok=True)
doc = fitz.open(str(pdf_path))
for page_no in [12, 14, 18]:
    page = doc[page_no - 1]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    pix.save(out_dir / f"{pdf_path.stem}-p{page_no:03d}.png")
```

每次视觉读取约 10K–30K token，**默认只读 high 页**。分类复核页不等同于完整视觉读取：可先单页中低分辨率渲染，只判断版面和图表存在性，不提取图中文字细节；确认需要抽取结构后再按 high 页视觉补全。

`medium` 页的升级规则：

- 用户明确要求复核 medium 页。
- high 页视觉复核显示该页与相邻 medium 页共同构成同一流程/公式/案例/表格。
- 抽样 2–3 个 medium 页后发现文本抽取明显丢图中标签、公式结构、表格行列或箭头关系。

**1.4 — Sanity spot-check**

随机抽 2–3 张（标题页 + 1–2 张中段）用当前可用的视觉路径读一遍，校验你的 KP 提取是否反映幻灯实际内容。这一步抓三类问题：

- pdfplumber 返回空（纯图片 slide）
- 内容顺序判错
- 视觉强调（如 ==考点==、红框、加粗箭头）在纯文本里丢了

如果 spot-check 发现明显丢失，优先扩大到相关 high 页；只有证据显示 medium 页也丢关键结构时，才复核 medium 页。

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

Run `python3 scripts/check_kp_schema.py` — must pass.

## Report to User

> 已摄入 `<file>`：新增 KP `<n>` 个，增强已有 KP `<m>` 个，写入 detail cards `<k>` 张。审计见 `docs/ingest-003.md`。
> （Pool 现有 `<pool-count>` 个 KP；按 `inspect_state.py` 的下一步建议是 Stage B 重平衡，等你确认。）

**Do NOT auto-trigger Stage B.** Every stage transition needs propose-confirm.

## Don't

- 不要在 ingest 阶段给 KP 添加 `queue` 字段。`queue` 是 Stage B 的产物。
- 不要在 ingest 阶段写 `book/` 任何文件。
- 不要扔掉看似"次要"的细节——应试细节宁多勿少。
- 不要把同一个 PPT ingest 两遍——source-index 是 dedup 依据。如果用户明确说"重新摄入"，先 roll back 旧记录再做。
