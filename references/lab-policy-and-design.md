# Reference: Lab Policy and Design

Loaded when:
- Init asks about lab policy
- Stage B identifies a chapter cluster that should have a lab
- User explicitly says "设计实验 / 搞一下 lab"

> **Lab 不是必备组件。** 默认 `enabled: undecided`，遇到具体 lab 候选时再决定。

## When the lab module fires

| 场景 | 触发 |
|---|---|
| 初始化时设置 lab 政策 | initialize.md 询问 |
| Stage B 发现某簇适合配 lab | 在 rebalance audit 里建议；等用户确认才进 lab 模块 |
| 用户主动 | "给 chXX 加个 lab" 或 "设计实验" 等明确指令 |

**禁止**：在 Stage C 写章时自动连带创建 lab。Lab 是独立步骤，需要用户的注意。

## Lab Policy Schema

`spec/lab-policy.yaml`:

```yaml
enabled: true            # true | false | undecided
# 如果 enabled=false，下面字段都不必填
# 如果 enabled=undecided，可以仅记 preferences，等出现 lab 候选时再补完
defaults:
  required_or_optional: required   # required | optional | teacher_only
  expected_minutes: 60             # 30 | 45 | 60 | 90
  needs_reference_solution: true
  needs_starter: true
  needs_verify_script: true
  target_env: linux                # linux | wsl | docker | any
preferences:
  course_focus: mechanism_understanding   # mechanism_understanding | exam_drill | engineering_practice
  toolchain: []                            # e.g. ["xv6", "nemu", "python", "c-posix", "command-observe"]
  forbidden: []                            # e.g. ["root", "network"]
note: |
  自由文本，记录用户对实验风格的偏好或避坑。
```

如果 `enabled: undecided`，可以只填 `note: "等出现 lab 候选时再决定"`。

## 课程化提问（不要用通用模板）

通用模板（仅作内部参考，**不要直接抛给用户**）：

- 是否包含 lab？
- 必做/选做/教师用？
- 期望时长？
- 是否需要 starter / solution / tests / verify？
- 目标环境？
- 偏机制理解、应试训练、还是工程实践？

**真正提问时必须用课程语境**。以下是 OS 课程的示例（其他课程要按学科改写）：

```
是否使用 Linux/WSL/Docker？
lab 偏命令观察、Python 模拟器、C/POSIX、xv6/Nachos/NEMU，还是混合？
是否要求学生写：
  - 系统调用包装
  - 调度器
  - 同步原语
  - 页表模拟
  - 文件系统模拟
单个 lab 期望时长？30 / 45 / 60 / 90 分钟
是否需要自动测试和参考解？
是否服务考试题型，还是偏真实系统实践？
```

非 OS 课程的提问模式应类比：用具体技术栈、具体工具、具体可观察现象提问，避免空泛的"什么风格的 lab"。

如果用户答"还没想好" → 接受 `undecided`，写：

```yaml
enabled: undecided
decision_required_before: first_lab_candidate
preferences:
  course_focus: <if hinted>
```

**不要**强迫用户在 init 阶段就决定所有 lab 细节。

## Lab 设计的内容流程

当 lab 真的要做（用户已批准 lab 政策 + Stage B 标了 lab 候选 + 用户进入 lab 模块）：

### 1. Lab 类型选择

按 lab-policy.yaml 的 `preferences.toolchain` 和章节性质决定：

| 类型 | 适用场景 | 学生时间 | 产物 |
|---|---|---|---|
| **observation** | 用现成工具观察现象（strace、top、ps） | 30 min | 命令清单 + 观察记录表 + 解释题 |
| **python-simulator** | 模拟算法行为（调度、页面替换） | 45 min | starter.py + TODO + solution.py + verify.py |
| **c-posix** | 系统调用/同步原语实操 | 60 min | C 源码 + Makefile + verify.sh |
| **mini-kernel** | xv6/Nachos/NEMU 修改 | 60-90 min | patch + 测试用例 |
| **observation+report** | 课堂阅读+表格填写（非编码） | 30 min | 表格 + 解释问题 |

### 2. Lab 目录结构

```
labs/
  labXX-slug/
    README.md            # 实验说明 (问题 → 任务 → 验证)
    starter/             # 学生起点 (仅 code labs)
    solution/            # 参考解 (隐藏给学生)
    tests/               # 自动测试 (如适用)
    verify.sh            # 一键验证脚本
    report-template.md   # 学生提交模板
```

observation 类型可以非常简化：

```
labs/
  labXX-slug/
    README.md            # 含命令 / 表格 / 问题
    expected-observations.md   # 教师参考答案
```

### 3. README 必备段落

参见 `spec/lab-template.md` 的完整模板。结构总览：

```markdown
# Lab XX: <标题>

## 学习目标
(2-3 条，对应章节核心 KP)

## 实验背景
(简短散文，连接到对应章节的开篇问题或机制)

## 你将做什么
(2-5 个 TODO，每个 TODO 一句话描述任务)

## 准备
(环境要求、文件位置、运行方法)

## 任务
### TODO 1: <任务名>
(具体描述 + 提示)
...

## 验证
(运行 `./verify.sh` 或 `python3 -m pytest tests/`)

## 报告要求
(用 report-template.md 提交; 提交什么 / 怎么提交)
```

### 4. 验证脚本约束

- 必须有 `verify.sh` (或等价的一行命令) 给参考解通过。
- 参考解必须真实运行通过——写 lab 前先跑通参考解，再写学生 starter。
- 学生 TODO 处的 starter 必须**通过编译/解析**但**不通过 verify**。

### 5. 例题与考题对齐（应试 lab 时）

按 `preferences.course_focus` 映射 lab TODO 与 KP：

| course_focus | TODO 来源 |
|---|---|
| `exam_drill` | KP 的 `detail_cards.type=exam_tip` 或 KP 的 `role=exam_pattern` |
| `mechanism_understanding` | KP 的 `role=mechanism` (实现机制核心步骤) |
| `engineering_practice` | KP 的 `detail_cards.type=operation` (真实系统命令/调用) |

混合时分主次：标 `主轴: mechanism_understanding`，少量 `exam_drill` TODO 作 bonus。

### 6. Cleanup 与 checks

```bash
python3 scripts/check_lab.py labs/labXX-slug/
```

校验 README 完整、verify.sh 可执行、（如适用）solution 跑通。

## 何时把 Lab 拆成独立 skill

目前**不需要**。在以下情况出现前都保持 lab 作为本 skill 内部模块：

- lab 被多个教材项目复用 → 拆 `course-lab-designer` skill
- lab 复杂到独立维护（专门工具链、CI 流水、镜像构建）→ 拆
- 用户经常单独要求"只设计 lab，不写教材"→ 拆
- lab 涉及 xv6/NEMU/Docker 等需要稳定模板与脚本资产 → 考虑拆

## Write Boundaries

- ✅ `labs/labXX-slug/`（新建目录及其内容）
- ✅ `spec/lab-policy.yaml`（仅在初始化时或 `enabled: undecided → true/false` 切换时修改）
- ❌ `book/`（lab 不直接动正文；如要在正文链接 lab，由 Stage C 在写章时引用）
- ❌ 其他 spec 文件

## Don't

- 不要在 lab README 写日期或版本号。
- 不要把所有章节都强行配 lab。有些章本来就该是纯阅读章节。
- 不要让学生时长超过 90 分钟而不提示"分两次做"。
- 不要在 Stage C 自动连带创建 lab——lab 是独立决策。
- 不要给 observation 类型 lab 配复杂 verify 脚本（与类型不符）。
