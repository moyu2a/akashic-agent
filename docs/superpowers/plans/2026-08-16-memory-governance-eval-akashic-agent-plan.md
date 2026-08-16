# Memory Governance Evaluation for akashic-agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `akashic-agent` 中落地真实可运行、可审查、可复现的记忆召回与回答治理评测体系，用于严格解释 `37.5% -> 97.5%` 的同表因果链，并把 `98.75%` 明确记录为后续 safe-version system-path 的独立验证结果。

**Architecture:** 评测体系分为数据集层、语义审查层、剖面流水线层、评分层、报告层。数据集从隐式构造迁移为显式 JSONL；自动 self-check 负责格式、引用、证据图和冲突约束；20% 人工抽检负责确认 case 在人类常识下语义合理、可回答。P1-P4 通过独立 profile / pipeline 配置接入 `memory2.eval_comprehensive_online`，新增 P3 `chain_tri_evidence_only` 拆分结构化证据收益；评分采用确定性规则优先，语义仲裁只处理模糊边界。

**Tech Stack:** Python 3、pytest、现有 `memory2` 模块、现有 `AgentLoop` 在线评测链路、JSON/JSONL、Markdown 报告。

## Global Constraints

- 目标项目是 `/home/jjh/git_work/akashic-agent`。
- 所有实现、验证和真实评测执行必须在一个新建分支中执行；本次使用 `akashic-agent/.worktrees/memory-governance-eval-v2` 和分支 `feature/memory-governance-eval-v2`。
- 不覆盖用户当前未提交文档：`my_md/interview/08补充.md` 和 `my_md/interview/长时间背诵.md`。
- `37.5% -> 97.5%` 只能解释为同一份 comprehensive online eval 中 `chain_tri_retrieval` 到 `chain_tri_governed_answer_contract` 的主因果链。
- `98.75%` 只能解释为 `safe_version_replace_guided_with_retry_shadow` 的后续 system-path 独立验证。
- P3 `chain_tri_evidence_only` 必须独立存在：候选治理为真，结构化证据为真，回答契约为假。
- forbidden / 禁答泄露 / 旧值泄露是硬失败，不能被语义相似度仲裁覆盖。
- 主评测 deterministic 配置固定为 `temperature=0`、`top_p=1`、`seed=42`；报告中必须记录 seed 是否实际生效。
- 数据集进入正式评测前必须通过自动 self-check 和 20% 人工语义抽检 release gate。
- 正式 real LLM 结果必须使用 fresh checkpoint：新 checkpoint 路径必须不存在或为空，正式 run 禁止 `--resume`。

## Implementation Phases

- [x] Phase 0: 在新建分支/worktree 中执行，并确认 baseline 测试通过。
- [x] Phase 1: 新增 `memory_governance_eval_80.jsonl`、typed loader、自动 self-check、确定性 generator。
- [x] Phase 1.5: 新增 20% 人工语义抽检 release gate，固定 `audit_seed=42`、抽 16 条，超过 2 条语义荒谬则整批重生成。
- [x] Phase 2: 新增 `chain_tri_evidence_only` profile，确保 P3 有候选治理和结构化证据，但没有回答契约语言。
- [x] Phase 3: 将显式 80 case 数据集接入综合在线评测，新增 `--memory-governance-dataset`、`--profile-ladder memory_governance_p1_p4`、deterministic sampling flags、fresh checkpoint 校验和 metadata。
- [x] Phase 3.5: checkpoint row 增加 `run_provenance`，resume/report-only 忽略 command-shape mismatch，并暴露 mismatch/malformed counts。
- [x] Phase 4: 新增 opt-in semantic judge，默认 scorer 行为保持不变；forbidden 命中时不调用 semantic judge。
- [x] Phase 5: README 说明 Codex generator 的自动 self-check 与人工语义抽检分工。
- [x] Phase 6: 主评测命令固定 `--prompt-variants baseline --repeats 1`，并要求 real LLM + fresh checkpoint + audit pass 才能解释为正式质量结论。
- [x] Phase 7: 新增稳定性 summary helper，`sampling_robustness_range <= 0.05` 为 gate。
- [x] Phase 8: 新增 240 条问题扰动 JSONL 和可复现生成脚本。
- [x] Phase 9: 新增治理失败 bucket 归一化。
- [x] Phase 10: system-path safe-version 报告增加 `claim_boundary` 和 `not_same_table_with`。
- [x] Phase 11: 新增最终报告和面试回答。
- [x] Phase 12: 执行 targeted verification。

## Formal Main Run Command

```bash
AKASHIC_RUN_LIVE_SMOKE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-governance-p1-p4-real-v1-workspace \
  --memory-governance-dataset my_md/memory_optimization/datasets/memory_governance_eval_80.jsonl \
  --profile-ladder memory_governance_p1_p4 \
  --deterministic \
  --temperature 0 \
  --top-p 1 \
  --seed 42 \
  --prompt-variants baseline \
  --repeats 1 \
  --out-dir my_md/memory_optimization/eval_reports/memory_governance_p1_p4_real_v1 \
  --config config.toml \
  --enable-real-llm \
  --checkpoint-jsonl /tmp/akashic-memory-governance-p1-p4-real-v1.checkpoint.jsonl \
  --fresh-checkpoint \
  --include-answer-debug \
  --answer-debug-dir /tmp/akashic-memory-governance-p1-p4-real-v1-workspace/answer_debug
```

## Report Metrics

主报告按 profile 输出 `cases`、`answer_success`、`grounding_success`、`forbidden_cases`、`answer_rate`、`grounding_rate`、`forbidden_rate`、`avg_tokens`、`avg_latency_ms`。可信度 metadata 必须包含 real/fake provider 状态、fresh checkpoint 状态、provider error/timeout/malformed/mismatch counts、deterministic sampling 配置、semantic audit release decision，以及 `37.5 -> 97.5` 和 `98.75` 的 claim boundary。
