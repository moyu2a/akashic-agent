# Memory Next Session Handoff Prompt

下面这段可以直接复制到新会话，用于继续当前 `memory-next` 分支的 memory optimization 工作。

```text
你现在接手 `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`，分支是 `memory-next`。请先阅读并遵守以下上下文：

1. 先检查当前 worktree 和文档：
   - `git branch --show-current`
   - `git status --short`
   - `my_md/memory_optimization/README.md`
   - `progress.md`
   - `my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1/evidence_prompt_ab_report.md`
   - `my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1/system_path_variant_failure_attribution.md`
   - `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/system_path_validation_intent.md`
   - `my_md/memory_optimization/eval_reports/p6o15_system_path_answer_lift_handoff_v1/system_path_answer_lift_handoff.md`
   - `my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/best_profile_production_candidate_summary.md`
   - `my_md/memory_optimization/eval_reports/p6o11_cross_report_synthesis_v1/cross_report_synthesis.md`

2. 重要边界：
   - 不要回退用户或前序会话的未提交改动。
   - 不要删除、覆盖或整理受保护的 untracked 目录：
     `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/`
   - 生产默认仍保持 `MemoryConfig.safe_version_governed_mode = "off"`。
   - 不要默认开启 graph-all-on、真实 retry/fallback、生产写入变更或全局 system prompt 变更。
   - 报告必须脱敏：不要写入 raw query、raw prompt、session text、memory summary、full answer、API key、Authorization 或 secret。

3. 当前关键结论：
   - 当前 system-path 最佳 practical mode 是 `safe_version_replace_guided`。
   - P6o-18 真实小矩阵结果：
     - `safe_version_replace`: `24/40 = 60.0%`
     - `safe_version_replace_guided`: `31/40 = 77.5%`
     - `safe_version_replace_structured_guided`: `31/40 = 77.5%`
     - `safe_version_replace_near_query_block`: `23/40 = 57.5%`
     - grounding 全部 `100.0%`
     - forbidden 全部 `0.0%`
   - P6o-18 failure attribution 结论：
     - 错误集中在 answer layer，不是 memory layer。
     - infra 干净：provider error `0`，timeout `0`。
     - guided 剩余 `9/40` miss：required-term miss `5`、any-group miss `2`、language failure `2`。
     - `structured_guided` 没有净增益：修复 `4` 个 guided miss，同时回退 `4` 个 guided pass，且 token/latency 更高。
     - `near_query_block` 明显退化：丢失 `10` 个 guided 已答对 case，只修复 `2` 个 guided miss。

4. side conversation / handoff 中记录过的可继续方案：
   - P6o-6 Combination Guidance：
     以 `chain_tri_governed_answer_contract` 为 baseline，一层一层测试：
     `tri governed` vs `tri + rerank governed`，
     `tri governed` vs `tri + version-boundary governed`，
     `tri + rerank + version-boundary governed`，
     最后才考虑 `tri + rerank + version-boundary + routed graph governed`。
     目的：避免 graph/version/rerank 一次全混导致噪声。
   - P6o-13 System-Path Real LLM Validation Intent：
     验证最佳方案进入真实 system path 后，用测试集驱动真实 LLM 调用，是否还能保持效果。
     目的不是 eval-only 上限验证，也不是生产自然流量。
   - P6o-15 to P6o-19 System-Path Answer Lift Roadmap：
     P6o-15 repeat stability + failure attribution 已完成；
     P6o-16 answer guidance 已完成；
     P6o-17 guided repeat stability 已完成；
     P6o-18 evidence prompt A/B 已完成；
     P6o-19 原方向是组合验证：`safe_version_replace`、`safe_version_replace_guided`、`safe_version_replace_guided_with_retry_shadow`。

5. 当前更合理的下一步候选：
   - 不要继续推进当前 `structured_guided` 或 `near_query_block` wording。
   - 不要扩大召回或 graph-all-on 来解释 P6o-18 的剩余 miss。
   - 优先考虑 P6o-19 system-path combination validation：
     `safe_version_replace_guided + post-check retry shadow`，
     只记录 shadow telemetry，不真实 retry，不改变用户可见回答。
   - 如果用户要求 prompt 调整，再围绕 guided 的 9 个 miss 做 targeted answer-selection / language compliance 小矩阵。

6. 如果要制定 plan：
   - 先调用 plan skill / writing plan skill；
   - 再调用 review skill 审阅；
   - 修订后执行；
   - 每一步都要记录测试方法、数据、结论到文档；
   - 真实 LLM 测试前先 fake smoke，真实结果需要 checkpoint、rebuild、privacy scan 和 `git diff --check`。

请先简要复述你从文档读到的当前状态、可继续方案和你建议的下一步，不要立刻改代码，除非我明确要求执行。
```

