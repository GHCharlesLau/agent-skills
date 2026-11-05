---
name: "paper-replication"
description: >-
  Plan and scaffold a complete paper replication + extension project. Given a paper, produce a
  full `INSTRUCTIONS.md` master workflow (Phase 0..N with 🛑 stop-and-check checkpoints), a
  cross-agent `AGENTS.md` context file, and scaffolding (`00_setup.py`, `utils.py`,
  `requirements.txt`, `.env.example`, directory layout) so an agent can replicate and extend the
  paper step by step. Strict anti-hallucination rules: table values are filled from the PDF during
  execution, formulas transcribed verbatim, citations verified. Use when the user wants to
  replicate a paper / reproduce results / run a replication study / 复现论文 / 论文复现 / 结果复现 /
  复现研究.
---

# paper-replication

你是一位学术论文复现规划师（academic paper replication planner）。给定一篇论文，产出完整的 `INSTRUCTIONS.md`，指导 AI agent 逐步复现并扩展该论文。

## 输入解析

解析用户的输入，提取：
- **论文标题**（必填）
- **作者与年份**（必填）
- **PDF 位置**（必填）— 文件路径或 URL
- **数据来源 / 复现仓库**（可选）
- **扩展想法**（可选；缺省时根据论文局限自行提出）

任一必填项缺失时，先询问用户再继续。

## 工作流

### Step 1: 阅读并分析论文

**优先用 MinerU（`mineru-document-extractor` skill）把 PDF 转成 Markdown/结构化文本**，以获得精确的表格与公式，再逐段精读并提取结构化笔记：

1. **研究问题** — 论文回答的因果/预测问题
2. **方法** — 识别变异来源、估计器或算法
3. **数据** — 来源、时间范围、分析单元、关键变量、样本量
4. **关键设定** — 主要方程或算法及其记号
5. **结果表格** — 每个：名称、列、行、关键系数标签
6. **图表** — 每个：类型、坐标轴、展示内容
7. **稳健性检验** — 补充分析
8. **局限性** — 作者声称无法做到的部分
9. **扩展方向** — 通过以下途径识别：(a) 作者承认的空白；(b) 引用本论文且提出改进的后续论文（用 websearch / `agent-reach` 检索 "cited by"）；(c) 发表后可用的新方法或新数据集；(d) 未探索的实际约束（如可扩展性、跨域迁移）

**反幻觉规则（严格遵守）**：

- **表格**：只记录结构（列/行标签、度量内容）。不要填具体数值——数值将由执行 agent 在 Phase 1 直接从 PDF 读取。所有数值单元格写 `[FILL DURING PHASE 1 FROM PDF]`。
- **公式**：逐字转写论文中的数学记号。保留所有下标、上标、希腊字母。OCR 有歧义时标 `[VERIFY FROM PDF]`。
- **算法/伪代码**：原样重现变量名与控制流。不得改名、简化或"改进"记号。
- **引用**：每条引用标注 `[VERIFIED]` 或 `[UNVERIFIED]`。仅当在本步用 web 检索确认真实存在时才是 `[VERIFIED]`。未验证的引用仍须列出但明确标记。
- 无法以高置信度从 PDF 确认的细节写 `[CONFIRM FROM PDF]`，不要猜。

**交叉引用检查**：每个公式与数值结果，确认在摘要、方法、结果三部分一致出现。在 "Verification Notes" 中列出所有不一致。

### Step 2: 定位数据与代码

1. 检索复现材料（数据可用性声明、OSF、GitHub、补充材料）
2. 若存在复现代码：检查以核对变量名、样本构造与设定
3. 若无复现代码，明确写出："No replication code found. Agent will implement from scratch based on paper description."
4. 确定原始编程语言及需要的转译（如 Stata → Python）

**不要编造仓库 URL。** 找不到复现材料就明说。

### Step 3: 生成 INSTRUCTIONS.md

按 Step 4 的模板写入完整 `INSTRUCTIONS.md`，把 `{{PLACEHOLDER}}` 替换为提取内容，然后生成脚手架文件（Step 5）。

### Step 4: 创建目录结构与脚手架

```
{{PROJECT_SLUG}}/
├── INSTRUCTIONS.md          # 主工作流（核心交付物）
├── AGENTS.md                # 跨 agent 仓库上下文（Claude Code / Codex / Cursor / OpenCode 通用）
├── CLAUDE.md                # 可选：Claude Code 专属别名/增强
├── original/
│   ├── paper/               # 源 PDF
│   ├── code/                # 原始复现代码（如有）
│   └── data/raw/            # 原始数据下载
└── {{WORKING_DIR}}/         # 所有代码与输出放在这里
    ├── requirements.txt
    ├── .env.example
    ├── code/
    │   ├── 00_setup.py
    │   └── utils.py
    ├── data/{raw,processed,extension}/
    ├── notes/
    ├── models/
    ├── output/{tables,figures,paper}/
    └── logs/
```

**CRITICAL**：`00_setup.py` 必须把 `PROJECT_ROOT` 解析到工作目录：

```python
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```

生成这些文件：

**`00_setup.py`** — 路径常量（DATA_RAW、DATA_PROCESSED、NOTES_DIR、OUTPUT_TABLES、OUTPUT_FIGURES、OUTPUT_PAPER、LOGS_DIR、MODELS_DIR）、python-dotenv 加载 .env、随机种子初始化（默认 42）、自动创建输出目录、Step 1 提取的论文特定常量。

**`AGENTS.md`** — 项目概览、仓库结构、关键技术上下文（算法、超参数、数据摘要）、工作流规则（阶段顺序、检查点要求）、依赖、编码约定。**不要**把论文特定执行细节放这里——那些属于 `INSTRUCTIONS.md`。（若用户主用 Claude Code，可额外生成 `CLAUDE.md` 作为别名或增强。）

**`.env.example`** — 带注释的模板，列出需要的 API key。

**`requirements.txt`** — 全部识别出的依赖。

### Step 5: 初始化版本控制

- `git init`，首次提交脚手架。
- 每个检查点（Checkpoint）后提交一次，提交信息用 `Phase N checkpoint`。
- 全部完成后打 tag（`v1.0-replication`）。

### Step 6: 呈现摘要

打印：阶段划分、关键表格/图表、数据来源、扩展方向、下一步。

---

## INSTRUCTIONS.md 模板

填写每个 `{{PLACEHOLDER}}`。删去不适用章节；按需增补。Phase 0–2 与论文写作使用下方固定结构。方法特定阶段（Phase 2 与论文写作之间）遵循同样的检查点模式，但任务为论文特定内容。

```markdown
# Replicating and Extending "{{PAPER_TITLE}}"

## Project Overview

Replicate and extend {{AUTHORS}} ({{YEAR}}). {{ONE_PARAGRAPH_SUMMARY}}.

**Tasks**: 1) Replicate using {{DATA_SOURCE}}  2) {{TASK_2}}  3) Extend by {{EXTENSION}}.

**Original paper**: {{CITATION_OR_URL}}
{{DATA_SOURCE_LINE}}

**Replication success criteria**: {{SUCCESS_CRITERIA}} — e.g., 点估计落在原论文 ±1 标准误内、符号与显著性一致；对确定性算法要求数字一致。

---

## Stop-and-Check Protocol

每个阶段以强制的 🛑 检查点结束。在每个检查点：
1. 总结已完成内容
2. 提交交付物供审阅
3. 列出问题与顾虑
4. **关键修正（Critical Corrections）**：改变方法路径的发现（数据不匹配、公式出入、代码偏离论文）
5. **等待人工批准**后再继续
6. `git commit` 记录本阶段

---

## PHASE 0: Project Setup

### Task 0.1: 创建目录结构（见模板规范）
### Task 0.2: 下载原始材料 — {{DOWNLOAD_INSTRUCTIONS}}
### Task 0.3: 检视原始数据与代码 — 记录文件清单、维度对照论文数字、变量定义、代码工作流、语言转译计划。保存到 `notes/original_materials_review.md`。
### Task 0.4: 环境设置 — {{ENVIRONMENT_REQUIREMENTS}}

## 🛑 CHECKPOINT 0
确认：结构已创建、材料已下载、数据已检视、环境已配置。
交付：`notes/original_materials_review.md`、数据文件清单、`requirements.txt`。
Critical Corrections: ____

---

## PHASE 1: Literature Review

### Task 1.1: 总结原论文 — 保存到 `notes/original_paper_summary.md`：
- 研究问题、带公式的方法、数据、关键结果（**仅表格结构**——数值在本阶段直接从 PDF 读取填写，不预填）、稳健性、局限性。

### Task 1.2: 文献综述 — 检索并验证每条引用。创建 `notes/literature_review.md` 表格：Authors | Year | Journal | Key Finding | Verified?
**只保留已验证引用。** 未验证的标记 `[UNVERIFIED]`。

### Task 1.3: 扩展论证 — 保存到 `notes/extension_rationale.md`。

## 🛑 CHECKPOINT 1
确认：论文已总结、公式已交叉引用、引用已验证、扩展已记录。
交付：三个 notes 文件。
Critical Corrections: ____

---

## PHASE 2: Data Preparation

### Task 2.1: 加载并检视数据 — 维度、变量、缺失值
### Task 2.2: 复现汇总统计 — 对照论文 Table {{N}}（数值直接从 PDF 读取，不要相信预填数字）
### Task 2.3: 数据清洗与变量构造 — {{SPECIFIC_STEPS}}
### Task 2.4: 训练/验证/测试划分 — {{SPLIT_STRATEGY}}

## 🛑 CHECKPOINT 2
确认：数据已加载、汇总统计与论文一致（或已记录出入）、变量已构造。
交付：汇总表（你的 vs 论文的）、数据质量报告。
Critical Corrections: ____

---

## PHASE {{3}}: {{METHOD_TITLE}}

{{METHOD_SPECIFIC_TASKS}}

## 🛑 CHECKPOINT {{3}}
确认：{{METHOD_CHECKLIST}}。
交付：{{METHOD_DELIVERABLES}}。
Critical Corrections: ____

---

[按需重复更多方法特定阶段]

---

## PHASE {{N-1}}: Paper Writing

章节：Abstract (150–200w)、Introduction (~1500w)、Background (~1500w)、Data (~1000–1500w)、Methodology (~1500–2500w)、Results (~2000–3000w)、Discussion (~1000w)、Tables and Figures、References。

## 🛑 CHECKPOINT {{N-1}}
交付：完整论文草稿、全部表格/图表、参考文献。
Critical Corrections: ____

---

## PHASE {{N}}: Final Deliverables

### Task: 组织代码（编号脚本 00–09 + utils.py）、跑通全流程、创建 README.md。

## 🛑 FINAL CHECKPOINT
确认：论文、代码、数据、文档齐全。

---

## PHASE {{N+1}}: Replication Report（新增）

### Task: 生成 `replication_report.md`，逐项对比 论文数字 vs 复现数字：
| Statistic | Paper | Replicated | Match? |
|-----------|-------|------------|--------|
- 覆盖所有关键表格、图、稳健性检验
- Match? 判定依据 Step 0 的 success criteria
- 不匹配项必须解释差异来源（数据版本、设定差异、bug 等）
- 复现成功/部分成功/失败的总体结论

## 🛑 CHECKPOINT {{N+1}}
交付：`replication_report.md`、git tag `v1.0-replication`。
Critical Corrections: ____

---

## Appendix: Original Paper Key Results

### Table {{N}}: {{TABLE_DESCRIPTION}}
| Column | Row | Paper Value | [FILL DURING PHASE 1 FROM PDF] |
|--------|-----|-------------|----------------------------------|

[对所有表格与图表重复 — 仅结构，不预填数值]

---

## Quality Standards

- **Statistical**: 点估计带 SE 与 CI；适当的聚类；正确的零假设解读；报告种子
- **Writing**: 主动语态；变量首次出现时定义；记号一致
- **Reproducibility**: 所有结果来自代码；无手工步骤；API key 只从 .env 读取；路径相对 PROJECT_ROOT
- **Citations**: 每篇引用经 web 检索验证；无幻觉引用；APA 格式含 DOI
```

---

## 输出规范

1. `{{WORKING_DIR}}/INSTRUCTIONS.md` — 核心交付物（填好的模板）
2. `{{PROJECT_ROOT}}/AGENTS.md`（+ 可选 `CLAUDE.md`）— 伴生上下文文件
3. `{{WORKING_DIR}}/code/00_setup.py` — 设置脚本
4. `{{WORKING_DIR}}/code/utils.py` — 共享工具占位
5. `{{WORKING_DIR}}/requirements.txt`
6. `{{WORKING_DIR}}/.env.example`
7. 全部目录已创建
8. `{{WORKING_DIR}}/notes/replication_report.md` — 复现对比报告（最后一个 Phase 生成）

## 关键约束

- **反幻觉优先**：表格数值、公式、算法记号、引用一律按 Step 1 规则处理，禁止猜测
- **不编造仓库/数据 URL**：找不到就明说
- **PDF 解析优先用 MinerU**：复杂表格与公式用 `mineru-document-extractor` 转 Markdown 再精读
- **引用验证用 websearch / agent-reach**：`[VERIFIED]` 必须来自真实检索
- 每个检查点必须 `git commit`；最终打 tag
- 复现报告必须解释每一处数字差异
