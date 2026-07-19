# Memory Quantitative Chain Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 memory 量化评测从“只给分数”补齐为“能复盘的链路评测报告”，清楚展示每个开关关闭/开启后的表现、问题和结论。

**Architecture:** 继续复用 Phase 6d 的离线确定性评测链路，不新增真实 LLM 调用，不读写真实 memory 数据库。报告生成逻辑仍集中在 `memory2/eval_quantitative_uplift.py`，测试覆盖 CLI 产物，项目说明文档只做索引和解释。

**Tech Stack:** Python、pytest、Markdown、现有 `EvalCase` / `EvalRunReport` / shadow trace 评测模型。

## Global Constraints

- 本轮只处理 `memory_quantitative_uplift` 详细复盘，不混入真实 LLM sample 相关改动。
- 所有结论必须标明是离线确定性评测，不宣称为生产真实效果。
- 指标必须解释清楚：`main_score`、`answer_rule_pass_rate`、`memory_grounding_pass_rate`、`forbidden_violation_rate`、token 信号和 common/hard 样本含义。
- 每个开关必须给出关闭时做得好、关闭时做得不好、开启后做得好、开启后做得不好、结论。
- 验证必须至少包含 focused pytest、compileall 和 `git diff --check`。

---

### Task 1: 生成可复盘的量化 Markdown 报告

**Files:**
- Modify: `memory2/eval_quantitative_uplift.py`
- Generate: `my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.md`

**Interfaces:**
- Consumes: `QuantitativeUpliftReport`、`QuantitativeProfileSummary`、`PROFILE_FEATURE_LABELS`
- Produces: `_detailed_review_lines(report, rows) -> list[str]`、`_review_metric_row(label, row) -> str`、`_profile_review_text(profile_name) -> dict[str, str]`

- [x] **Step 1: Add detailed review section generator**

Add `_detailed_review_lines()` after `write_quantitative_uplift_markdown()` helpers. It must append:

```python
lines.extend(_detailed_review_lines(report, rows))
```

The generated Markdown must include:

```markdown
## 详细复盘
### 测试过程
### 指标含义
### 各开关详细结论
```

- [x] **Step 2: Add per-profile review text**

Add review copy for:

```python
(
    "off",
    "write_value_only",
    "tri_retrieval_only",
    "graph_only",
    "rerank_only",
    "version_provenance_only",
    "sleep_only",
    "all_on",
)
```

Each profile must output five fields:

```python
"off_good"
"off_bad"
"on_good"
"on_bad"
"conclusion"
```

- [x] **Step 3: Regenerate Markdown report**

Run the existing report generation path so `my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.md` contains the new detailed review.

Expected output:

```text
## 详细复盘
### 指标含义
#### 三路召回 `tri_retrieval_only`
```

### Task 2: 测试 CLI 产物包含详细复盘

**Files:**
- Modify: `tests/test_memory_quantitative_uplift_cli.py`

**Interfaces:**
- Consumes: CLI output file `memory_quantitative_uplift_eval.md`
- Produces: regression assertions for detailed Markdown sections

- [x] **Step 1: Read generated Markdown in CLI test**

Add:

```python
markdown = md_path.read_text(encoding="utf-8")
```

- [x] **Step 2: Assert required sections exist**

Add assertions:

```python
assert "## 详细复盘" in markdown
assert "### 指标含义" in markdown
assert "#### 三路召回 `tri_retrieval_only`" in markdown
```

- [x] **Step 3: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_quantitative_uplift.py tests/test_memory_quantitative_uplift_cli.py -q
```

Expected:

```text
13 passed
```

### Task 3: 更新项目文档索引

**Files:**
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`

**Interfaces:**
- Consumes: generated report path `my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.md`
- Produces: a clear note telling future readers where to review process, metrics, per-switch data, and conclusions

- [x] **Step 1: Add report index note**

Add:

```markdown
其中 `memory_quantitative_uplift_eval.md` 已补充“详细复盘”章节，记录测试过程、每个指标的含义、每个开关的 overall/common/hard 数据、关闭时做得好/不好、开启后做得好/不好，以及最终结论，便于后续复盘时直接查看。
```

- [x] **Step 2: Keep scope limited**

Do not edit unrelated memory optimization docs in this task.

### Task 4: 审阅和验证

**Files:**
- Review: `docs/superpowers/plans/2026-07-19-memory-quantitative-chain-review.md`
- Review: `memory2/eval_quantitative_uplift.py`
- Review: `tests/test_memory_quantitative_uplift_cli.py`
- Review: `my_md/memory_optimization/02-memory-quality-metrics.md`
- Review: `my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.md`

**Interfaces:**
- Consumes: git diff and generated Markdown
- Produces: review conclusion and verification result

- [x] **Step 1: Review plan alignment**

Check:

```text
是否覆盖用户要求：计划、审阅、执行、窗口输出结果、总结结论、发现问题后修订。
```

- [x] **Step 2: Review implementation diff**

Check:

```bash
git diff -- memory2/eval_quantitative_uplift.py tests/test_memory_quantitative_uplift_cli.py my_md/memory_optimization/02-memory-quality-metrics.md my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.md
```

Expected:

```text
Only detailed review generation, CLI assertions, docs index note, and regenerated report changed.
```

- [x] **Step 3: Run verification**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_quantitative_uplift.py tests/test_memory_quantitative_uplift_cli.py -q
.venv/bin/python -m compileall memory2 scripts tests -q
git diff --check
```

Expected:

```text
14 passed
compileall exits 0
git diff --check exits 0
```

- [x] **Step 4: Summarize result**

Report:

```text
本轮完成了链路评测复盘落档；当前量化结论仍来自离线确定性样本，不是真实 LLM 线上效果；下一步若要继续提高分数，应优先做组合权重和 active 化策略。
```

### Review Fixes

审阅发现的问题和处理结果：

- [x] 样本规模不能硬编码为 80/common 40/hard 40。已改为从 `report.metrics` 动态读取，`--case-set common --limit 8` 会输出 8/common 8/hard 0。
- [x] 报告生成函数不能硬编码“13 passed”。已改为说明测试结果以实际命令输出为准。
- [x] profile 文案里的关键分数不能写死。已改为从当前 `QuantitativeProfileSummary` 动态读取。
- [x] 各开关详细表需要展示 `token_signal_delta`。已补充表头和每行数据。
- [x] CLI 测试需要覆盖详细复盘的关键结构。已补充测试过程、指标含义、8 个 profile、五类结论字段、子集样本规模和非硬编码测试结果断言。
- [x] 工作树里存在 LLM sample 等无关未提交改动。本轮不删除、不回滚，只在后续暂存/提交时限定目标文件。
- [x] 子集报告中未评测的 hard/common 指标不能显示为 0。已改为 `unavailable`，避免把“没测”误读为“得分为 0”。
- [x] 子集报告文案不能说“hard 集为 unavailable，说明难例有效”。已改为“本次未评测 hard 集”，并补充回归测试。
