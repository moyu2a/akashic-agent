# Public Long Memory Benchmark Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `akashic-agent` 上接入公开长记忆评测，先执行 LongMemEval Phase A/Phase B，验证当前最强 P5 记忆治理结构在公开 benchmark 上的泛化表现。

**Architecture:** 公开集评测独立于 synthetic governance eval：新增 LongMemEval loader、分层抽样、question 级隔离 adapter、P5-only runner/scorer/report。Phase A 用 50 条分层样本验证全链路和评分口径，Phase B 在 Phase A gate 通过后运行 full；LoCoMo 与 LongMemEval-V2 只记录为后续保留项。

**Tech Stack:** Python 3、pytest、现有 `memory2` 评测模块、现有 AgentLoop online eval、JSON/JSONL、Markdown。

## Global Constraints

- 目标分支：`feature/memory-governance-eval-v2`。
- 目标 worktree：`/home/jjh/git_work/akashic-agent/.worktrees/memory-governance-eval-v2`。
- 执行公开集测试前必须先有 git checkpoint commit。
- 当前公开集测试只跑 P5 `chain_tri_governed_answer_contract`，不做 P1-P5 消融。
- LongMemEval 结果不能和 synthetic governance eval 混用指标。
- 每个 LongMemEval question 必须独立 eval scope，禁止跨 question memory 污染。
- Gold answer 永远不能写入 memory。
- 模型回答不能写回 memory。
- 所有 real LLM run 必须 fresh checkpoint。
- Phase C/Phase D 只记录，不执行。

## Phase Checklist

- [x] Phase 0: 创建公开集评测前 checkpoint commit。
- [ ] Phase 1: 保存并审阅本大 plan。
- [ ] Phase A: LongMemEval 50 条 stratified smoke，P5-only。
- [ ] Phase B: LongMemEval full，P5-only。
- [ ] Phase C: LoCoMo reserved，只记录不执行。
- [ ] Phase D: LongMemEval-V2 reserved，只记录不执行。

## Phase A Design

Phase A 是链路 smoke，不用于声明 full score。它必须覆盖 LongMemEval full 中的全部主要 category，因此采用 stratified sampling 而不是纯随机抽样。

Sampling:

- 从 LongMemEval full manifest 中读取 category 分布。
- 固定 `sample_size=50`、`seed=42`。
- 按 full category 比例分配样本数。
- 每个 category 至少抽 1 条。
- 报告记录 full category distribution、sampled category distribution、sample ids、seed。

Isolation:

- 每个 question 创建唯一 eval scope，例如 `longmemeval_phase_a_<source_id>`。
- 当前 question 的 history 只写入当前 scope。
- 当前 question 完成后，workspace/scope 不被下一题复用。
- Gold answer 不进入 memory。
- 模型回答不写回 memory。

Scoring:

- L1: normalized deterministic match。
- L2: independent semantic judge，用于 L1 失败且回答非空的同义回答仲裁。
- L3: semantic ambiguity list，人工抽检。
- Embedding similarity 只能作为辅助信号，不能单独决定 factual QA pass。

Phase A Gate:

- completed call count = 50。
- provider error count = 0。
- timeout count = 0。
- malformed checkpoint count = 0。
- scorer unable-to-score rate <= 10%。
- Markdown/JSON report 生成。
- 抽查至少 5 条 case，确认无 gold leakage、无 cross-question memory leakage。
- 任一 gate 失败，暂停并修订 Phase A plan，不进入 Phase B。

## Phase B Design

Phase B 在 Phase A gate 通过后执行 LongMemEval full，仍只跑 P5。

Phase B Gate:

- completed call count = full dataset question count。
- provider error count = 0。
- timeout count = 0。
- malformed checkpoint count = 0。
- checkpoint provenance mismatch count = 0。
- report 记录 dataset version/hash。
- report 按 category 输出 score。
- report 输出 failure samples 与 semantic ambiguity samples。
- 抽查至少 20 条 case：10 条 pass，10 条 fail 或 ambiguity。
- 报告声明该结果是 LongMemEval P5-only 公开 benchmark，不是 P1-P5 消融。

## Phase C / D Reserved

Phase C LoCoMo reserved:

- 只记录，不执行。
- 后续用于验证真实长对话、多 session、多事件时间线下的记忆泛化。
- 进入前必须明确 conversation ingestion 和 scoring 策略。

Phase D LongMemEval-V2 reserved:

- 只记录，不执行。
- 后续用于验证 agent workflow memory、environment state、长期任务经验记忆。
- 进入前必须已有 agent workflow memory 的正式接口和 scoring 口径。
