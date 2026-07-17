# Memory Optimization Docs

这个目录记录 `akashic-agent` 记忆系统的优化路线、指标体系和治理设计。

## 文档边界

- `architecture/04-memory-tools-plugins.md`：记录当前记忆、工具、插件的架构理解。
- `interview/08-architecture-diagram.md`：记录适合面试表达的系统链路和模块讲解。
- `memory_optimization/`：记录记忆系统后续怎么优化、怎么测、怎么治理。
- `governance/`：如果某个优化方向形成全局问题、设计取舍或复盘案例，再同步进入治理目录。

本目录不是当前实现状态说明。每篇文档都要明确区分：

- 当前已经具备的能力。
- 可以直接用现有数据测出来的指标。
- 需要新增埋点或评测集才能验证的能力。
- 后续设计方向，不代表已经实现。

## 文档列表

- [01-memory-optimization-roadmap.md](./01-memory-optimization-roadmap.md): 记忆系统优化总路线，整理当前能力、图片启发、优先级和阶段计划。
- [02-memory-quality-metrics.md](./02-memory-quality-metrics.md): 记忆质量指标清单，区分现有可测、加埋点可测、需要评测集才能测的指标。
- [03-memory-governance-design.md](./03-memory-governance-design.md): 记忆治理设计草案，覆盖写入门控、质量评分、冲突检测、检索重排和生命周期管理。
- [04-memory-plugin-experiment-roadmap.md](./04-memory-plugin-experiment-roadmap.md): memory 插件实验扩展路线，记录版本链、信息价值评分、三路召回、睡眠巩固、层级溯源，以及每项能力的开关和对比数据。

## 当前优化主题

参考图片中的“Agent 长时记忆中间件”，本项目可以吸收的核心不是具体技术栈或百分比指标，而是记忆治理思路：

- 写入前判断这条信息值不值得记。
- 写入后给记忆打质量分。
- 检索后不只按向量相似度排序，还要结合 scope、source_ref、时间、类型和置信度重排。
- 长期运行后要做去重、冲突检测、过期降权和压缩。
- 用 observe、Dashboard 和评测集验证优化是否真的有效。

## 当前执行位置

当前 memory 实验路线不是单点功能，而是一组按阶段推进的插件化实验能力。

已经完成：

- Phase 0：`memory_experiments` 实验配置、shadow trace 和运行态 smoke。
- Phase 1a：显式 `memorize` 的写入价值 shadow 评分结构化输出。
- Phase 1b：候选记忆和已有 active 记忆的只读对比，输出信息熵、新颖度、重复风险和写入减少率。
- Phase 2a：三路召回 + RRF 融合 shadow，记录语义、关键词、溯源三路候选和实验融合结果，不改变真实召回和 prompt 注入。
- Phase 2b：NetworkX 实体图谱 graph shadow，记录 graph lane、graph-augmented RRF 融合结果和图谱路径指标，不改变真实召回和 prompt 注入。
- Phase 3a：召回质量重排 shadow，记录 rerank 后的候选顺序、分数拆解和名次变化，不改变真实召回和 prompt 注入。
- Phase 3b：注入治理 shadow，记录 baseline 与 experimental 的注入差异、丢弃原因和 prompt 预算变化，不改变真实召回和 prompt 注入。
- Phase 4a：因果一致性版本链 shadow，基于 `memory_items.status`、`memory_replacements` 和本轮 baseline recalled items 构建 replacement-only 版本链，记录旧版本误召回、当前叶子、冲突链和回滚候选，不改变真实召回和 prompt 注入。
- Phase 4b：层级化溯源 shadow，解析现有 `source_ref` 和 scope 字段，记录来源覆盖、解析成功率、孤儿记忆、扫描级跨 scope 数量和本轮召回级跨 scope 风险；第一版不执行真实 `fetch_messages` 回源。
- Phase 5：离线睡眠巩固 shadow dry-run，在 `ConsolidationCommitted` 事件后有界扫描 active memory，记录重复、可合并、过期、低价值、冲突、缺失 source_ref 和预计 token 节省；不合并、不删除、不修改真实召回和 prompt 注入。
- Phase 6a-1：记忆评测集 schema 和第一批静态 fixture，定义 `off`、`phase1`、`phase2`、`phase3`、`phase4`、`phase5`、`all` 配置矩阵，以及 9 个覆盖 Phase 1-5 的离线 case；本阶段只做 loader、schema 校验和 fixture 校验，不运行 Agent，不调用 LLM，不写真实 memory DB。
- Phase 6a-2：离线 eval runner 和 JSON report writer，读取同一批 fixture，按 `off`、单阶段 profile 和 `all` 跑 deterministic profile 对照，校验 required / forbidden trace、metric key、should recall / should-not recall；不启动 Agent，不调用 LLM/embedding，不写真实 memory DB 或 observe DB。
- Phase 6b-1：真实 memory 数据只读采样器、真实样本到 EvalCase 的转换、unforced candidate 指标和 CLI 报告；严格使用 raw sqlite read-only + `PRAGMA query_only=ON`，不启动 Agent，不调用 LLM/embedding，不写真实 DB，报告默认不包含真实记忆正文。
- Phase 6b-2：真实 `AgentLoop` dry-run，使用临时 workspace、真实 `SessionManager`、真实 `DefaultMemoryRetrievalPipeline`、真实 `EventBus` / `TurnCommitted`，但 LLM 是 fake provider，memory engine 是受控测试 engine；不调用真实 LLM/embedding，不写真实 workspace，不代表最终回答质量。
- Phase 6b-3：显式门控的 LLM 小样本答案级评测，复用真实 `AgentLoop.process_direct()`、临时 workspace 和受控 memory engine；默认禁止真实 LLM，必须通过 `--enable-real-llm` 才能构造真实 `LLMProvider`。本轮已用 fake provider 跑通 3 个稳定答案级 case，报告记录答案规则命中、记忆 ID 使用、延迟、token 元数据和脱敏审计。

后续还有 1 个主要方向：

1. Phase 6：在真实 LLM 小样本稳定后，继续补 Dashboard 展示、连续评测和 active 化决策。

trace 汇总报告是这些阶段的数据出口，不应替代上述实验方向。

Phase 1b 的验证结论：

- focused suite：`30 passed`。
- live smoke：`3 passed`。
- `compileall`：通过。
- `git diff --check`：通过。
- live smoke 在 Python 3.14 环境下出现过 asyncio transport 析构 warning，但测试结果为通过，当前未作为 Phase 1b 功能失败处理。

Phase 2a 的验证结论：

- focused suite：`46 passed`。
- broader memory experiment suite：`51 passed`。
- `compileall`：通过。
- `git diff --check`：通过。

Phase 2b 的验证结论：

- focused suite：`56 passed`。
- broader memory experiment suite：`77 passed`。
- `compileall`：通过。
- `git diff --check`：通过。

Phase 3a/3b 的验证结论：

- focused rerank / injection tests：通过。
- engine contract 回归：通过。
- full pytest：`1915 passed, 3 skipped, 3 warnings`。
- `compileall` 和 `git diff --check`：通过。

Phase 4a/4b 的验证结论：

- focused Phase 4 suite：`45 passed`。
- 版本链纯函数、溯源纯函数、实验 trace writer 和 engine contract 回归均通过。
- 仍然是 shadow-only，不改变真实写入、真实召回、真实 `recall_memory` 工具结果和 prompt 注入。
- broader memory suite：`136 passed, 3 skipped, 1 warning`。
- full pytest：`1915 passed, 3 skipped, 3 warnings`。
- `compileall` 和 `git diff --check`：通过。

Phase 5 的验证结论：

- 提交：`3492cf2 feat: add memory sleep consolidation shadow experiment`。
- focused suite：`49 passed`。
- broader memory suite：`151 passed, 3 skipped, 1 warning`。
- full pytest：`1930 passed, 3 skipped, 3 warnings`。
- `compileall` 和 `git diff --check`：通过。
- 代码审阅发现的 stale / low-value 候选未截断问题已修复，当前所有 trace 候选输出都有上限和截断计数。
- 仍然是 shadow-only / dry-run，不改变真实写入、真实召回、真实 `recall_memory` 工具结果和 prompt 注入。

Phase 6a-1 的验证结论：

- 新增 `memory2/eval_cases.py`，提供 eval case loader、schema 校验、phase target 列表和配置 profile 到真实 `memory_experiments` 开关的映射。
- 新增 `tests/fixtures/memory_eval_cases/`，包含 9 个静态评测 case：偏好召回、临时记忆污染、重复记忆、冲突记忆、模糊指代图谱召回、注入治理预算、跨 scope 隔离、过期记忆睡眠巩固、层级溯源。
- focused suite：`14 passed`。
- 当前只证明“评测数据结构和 case pack 是一致的”，还不能产出 off/on A/B 指标；runner 和报告生成留到下一阶段。

Phase 6a-2 的验证结论：

- 新增 `memory2/eval_runner.py`，提供 `run_eval_case()`、`run_eval_cases()`、`run_eval_case_files()` 和 `write_eval_report()`。
- runner 只构造内存中的 `EvalTrace` / `EvalRunReport`，复用已有 memory shadow 纯函数，并把 builder 输出归一化成 fixture 期待的 metric key。
- 9 个 fixture 全量运行通过：`case_count = 9`、`profile_count = 30`、`failed_profile_count = 0`、`trace_count = 30`、`profile_pass_rate = 1.0`。
- focused suite：`21 passed`。
- 当前结论是“Phase 1-5 的 shadow 能力已经可以在离线 fixture 上做 off/on trace 对照”。它仍然不是生产流量评测，不代表真实回答准确率、真实 `recall_at_k` 或答案 grounding 已经达标。

Phase 6b-1 的验证结论：

- 新增 `memory2/eval_real_samples.py`：只读加载真实 `workspace/memory/memory2.db`，采样 preference、procedure、cross_scope、version_chain 类真实 memory 样本，并转换成 `EvalCase`。
- 新增 `memory2/eval_real_candidates.py`：计算不使用 `should_recall_ids` 强制召回的 candidate 指标，显式标记 `label_forced_recall = False`。
- 新增 `memory2/eval_real_report.py` 和 `scripts/run_memory_real_sample_eval.py`：输出 `memory_real_sample_eval.json` 和 `.md`。
- 报告包含脱敏审计明细：`sample_records`、`profile_records`、`candidate_records`、`failure_records`，默认不写真实记忆正文。
- focused Phase6b suite：修订后 `19 passed`；Phase6a + Phase6b focused suite：修订后 `40 passed`。
- 本地运行结果：当前工作区和主仓库都没有 `workspace/memory/memory2.db`，CLI 正常生成降级报告并返回 exit code 1。
- 降级报告路径：`my_md/memory_optimization/eval_reports/memory_real_sample_eval.json` 和 `memory_real_sample_eval.md`。
- 降级报告摘要：`sample_count = 0`、`memory_item_count = 0`、`missing_table_count = 1`、`profile_count = 0`、`trace_count = 0`、`sample_records = []`、`profile_records = []`、`label_forced_recall = False`、`llm_calls_enabled = False`、`answer_quality_available = False`。
- 当前结论是“真实样本评测代码和报告链路已经具备；本机缺少真实 memory DB，所以还没有真实样本效果数据”。要得到真实数值，需要先提供或生成 `workspace/memory/memory2.db`。

Phase 6b-2 的验证结论：

- 新增 `memory2/eval_agent_dry_run.py`，通过真实 `AgentLoop.process_direct()` 跑 eval case。
- 新增 `scripts/run_memory_agent_dry_run_eval.py`，输出 `memory_agent_dry_run_eval.json` 和 `.md`。
- 本阶段使用 fake LLM 和受控 memory engine，只验证真实 turn pipeline 接线，不评估最终回答质量。
- 本地 dry-run 跑完 9 个 fixture case：`case_count = 9`、`passed_case_count = 9`、`failed_case_count = 0`。
- 集成指标：`agent_turn_count = 9`、`retrieval_request_count = 9`、`fake_llm_call_count = 9`、`turn_committed_count = 9`、`session_message_count = 18`。
- 隐私边界：`raw_query_included = False`、`raw_memory_summary_included = False`、`prompt_included = False`、`session_text_included = False`。
- 报告路径：`my_md/memory_optimization/eval_reports/memory_agent_dry_run_eval.json` 和 `memory_agent_dry_run_eval.md`。

Phase 6b-3 的验证结论：

- 新增 `memory2/eval_llm_sample.py`，提供答案期望解析、确定性答案评分、真实 `AgentLoop` 小样本 harness 和脱敏报告 writer。
- 新增 `scripts/run_memory_llm_sample_eval.py`，默认 gate 真实 LLM；未传 `--enable-real-llm` 且未传 `--fake-provider` 时返回 exit code 1 并只写 gated report。
- 首批答案级 case 只包含 3 个稳定样例：`cross_scope_isolation`、`preference_recall`、`vague_reference_graph`。`conflict_memory` 因当前存在两个互相冲突的 active 记忆，暂不进入答案质量评分。
- fake-provider 本地报告：`case_count = 3`、`passed_case_count = 3`、`failed_case_count = 0`、`answer_contains_pass_count = 5`、`expected_memory_used_count = 3`、`forbidden_contains_violation_count = 0`、`provider_error_count = 0`、`timeout_count = 0`。
- token 和延迟指标：`token_metrics_available = True`、`prompt_token_count = 60`、`completion_token_count = 30`、`total_token_count = 90`、`total_latency_ms = 56`、`avg_latency_ms = 18`。这些 token 数来自 fake provider，用于验证报告链路，不代表真实费用。
- 隐私边界：`raw_query_included = False`、`raw_memory_summary_included = False`、`prompt_included = False`、`session_text_included = False`、`full_answer_included = False`。
- 报告路径：`my_md/memory_optimization/eval_reports/memory_llm_sample_eval.json` 和 `memory_llm_sample_eval.md`。
- 当前结论是“答案级小样本评测链路已经具备，并且真实 LLM 调用有显式门控”。要得到真实模型质量和费用数据，需要人工确认后运行带 `--enable-real-llm` 的命令。

## 实验扩展原则

图片中的高级能力进入本项目时，应先作为 memory 插件实验能力，而不是直接写成已实现能力。每项实验都需要：

- 配置开关。
- baseline 和 experimental 对照。
- shadow / dry-run 模式。
- observe、Dashboard 或 eval report 输出测试数据。
- 数据验证后再切到 active。

## 后续更新提示词

```text
请根据本次记忆系统优化讨论/设计/实验结果，更新 my_md/memory_optimization 下相关文档；如果形成架构演进或设计取舍，请同步更新 my_md/governance/03-domain-evolution.md 或 05-design-decisions.md。
```
