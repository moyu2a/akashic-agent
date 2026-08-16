# Memory Governance Evaluation Final Report

## Summary

本实现把记忆回答评测拆成 P1-P4 profile ladder，并新增显式 80-case JSONL 数据集、自动 self-check、20% 人工语义抽检、P3 evidence-only profile、fresh checkpoint provenance、deterministic sampling metadata、opt-in semantic judge、扰动样本和 safe-version claim boundary。

`37.5% -> 97.5%` 只能来自同一份 comprehensive online eval 的 `chain_tri_retrieval -> chain_tri_governed_answer_contract` 主表。`98.75%` 只属于 `safe_version_replace_guided_with_retry_shadow` 的 system-path 独立验证。

本次正式 real LLM run 没有复现历史 `37.5% -> 97.5%`，而是在同一张 P1-P4 主表中得到新的实测值 `41.25% -> 100.0%`。

## Dataset

- 数据集路径：`my_md/memory_optimization/datasets/memory_governance_eval_80.jsonl`
- case 数：80
- scenario groups：8，每组 10 条
- generator：`memory2.eval_memory_governance_generator.generate_memory_governance_dataset(seed=42)`
- 自动 self-check：case/memory id 唯一、引用悬空、superseded 误召回、expected/forbidden 冲突、evidence graph 悬空和环。
- 人工语义抽检：`memory_governance_eval_80_semantic_audit.md`，固定抽 16 条，`release_decision=pass`。

## Main Profiles

- P1 `chain_tri_retrieval`：只看三路召回和融合结果。
- P2 `chain_tri_candidate_governance`：加入候选治理。
- P3 `chain_tri_evidence_only`：加入结构化证据区块，但不加入回答契约。
- P4 `chain_tri_governed_answer_contract`：候选治理 + production-safe evidence contract。

## Scoring

评分先执行 deterministic rules：expected terms、any groups、forbidden terms、grounding、language。forbidden 命中是硬失败，不进入 semantic judge。semantic judge 只在 opt-in 时处理模糊边界，并要求被测模型与仲裁模型异源。

## Formal Run Requirements

正式 real LLM 报告必须满足：`real_llm_enabled=true`、`fake_provider_enabled=false`、`provider_error_count=0`、`timeout_count=0`、`malformed_checkpoint_line_count=0`、`checkpoint_provenance_mismatch_count=0`、`skipped_from_checkpoint_count=0`、`fresh_checkpoint=true`。

主运行命令必须显式包含 `--prompt-variants baseline --repeats 1`，避免 runner 默认值放大 row count。若开启 answer debug，`--answer-debug-dir` 必须位于 `--workspace` 下，例如 `/tmp/akashic-memory-governance-p1-p4-real-v1-workspace/answer_debug`。

## Formal Run Result

- JSON report: `my_md/memory_optimization/eval_reports/memory_governance_p1_p4_real_v1/memory_comprehensive_online_eval.json`
- Markdown report: `my_md/memory_optimization/eval_reports/memory_governance_p1_p4_real_v1/memory_comprehensive_online_eval.md`
- Failure review: `my_md/memory_optimization/eval_reports/memory_governance_p1_p4_real_v1/memory_governance_failure_review.md`
- Full failure JSONL: `my_md/memory_optimization/eval_reports/memory_governance_p1_p4_real_v1/memory_governance_failure_review.jsonl`
- Checkpoint: `/tmp/akashic-memory-governance-p1-p4-real-v1.checkpoint.jsonl`
- Answer debug: `/tmp/akashic-memory-governance-p1-p4-real-v1-workspace/answer_debug`
- `chain_tri_retrieval`: 80 cases, answer rate 41.25%, grounding 100.0%, forbidden 17.5%.
- `chain_tri_candidate_governance`: 80 cases, answer rate 41.25%, grounding 100.0%, forbidden 0.0%.
- `chain_tri_evidence_only`: 80 cases, answer rate 26.25%, grounding 100.0%, forbidden 55.0%.
- `chain_tri_answer_contract`: 80 cases, answer rate 87.5%, grounding 100.0%, forbidden 12.5%.
- `chain_tri_governed_answer_contract`: 80 cases, answer rate 100.0%, grounding 100.0%, forbidden 0.0%.
