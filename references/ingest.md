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

### 1. Read the PPT (hybrid: text-first, then visual)

一份 PPT 通常 30–80 张幻灯片；整本视觉读会烧 50K–100K token。正确做法是**先用 pdfplumber 抓文本，再对图表页用 Read 工具视觉补全**。

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

这一步搞定 **~80% 的 KP 提取**：

- 每个 KP 的 `concept`、`role` 判定
- `detail_cards.type` ∈ {method, operation, exam_tip} 的 summary
- `source.slides` 字段的精确填写
- 标记好哪些 slide 含图（`[has images]`）供 1.2 用

如果环境没 pdfplumber：`pip install pdfplumber`（也是 `/pdf` skill 推荐的栈）。退化方案用 `pypdf` 也行，但 pdfplumber 的 page.images 检测更准。

**1.2 — Read 工具对图表页做视觉补全**

仅对 1.1 标了 `[has images]` 的 slide 用 Read 工具视觉读，捕捉 pdfplumber 抓不到的：

- `detail_cards.type=figure` 的内容（算法状态图、时序图、地址翻译图、磁盘结构图）
- 复杂表格（pdfplumber 表格抽取在多列/合并单元格上经常错）
- 视觉强调（颜色/框线/箭头表达的因果或对比）

调用形式：`Read(file_path="sources/ppts/<file>.pdf", pages="12-14")` 精确读特定页范围。每次 Read 约 10K–30K token，**只读真有图的页**。

**1.3 — Sanity spot-check**

随机抽 2–3 张（标题页 + 1–2 张中段）用 Read 视觉读一遍，校验你的 KP 提取是否反映幻灯实际内容。这一步抓三类问题：

- pdfplumber 返回空（纯图片 slide）
- 内容顺序判错
- 视觉强调（如 ==考点==、红框、加粗箭头）在纯文本里丢了

如果 spot-check 发现明显丢失，扩大相关区段的视觉读范围。

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
