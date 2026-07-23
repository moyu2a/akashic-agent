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
- [05-memory-target-metric-eval-plan.md](./05-memory-target-metric-eval-plan.md): Phase 6 后续目标指标评测口径，把回答效果、写入治理和记忆库卫生拆成三组百分比指标，并说明真实 LLM checkpoint 如何接入。
- [06-memory-320-baseline-plus-count-eval.md](./06-memory-320-baseline-plus-count-eval.md): 320 case 和 1000 case answer/retrieval-only 离线计数评测，使用原始记忆作为主基线，展示单模块增益和组合链路增益。
- [07-memory-write-governance-count-eval.md](./07-memory-write-governance-count-eval.md): 1200 个写入候选的离线写入治理计数评测，使用原本写入方式作为基线，展示离线集配置、写入减少、污染控制、误伤、漏拦、复核缺口和线上化边界。
- [08-memory-sleep-hygiene-eval.md](./08-memory-sleep-hygiene-eval.md): 睡眠巩固与记忆库卫生 evidence 评测，包含 standard、hard/adversarial、V3 安全候选口径、source-backed V1 真实来源证据评测、Phase 6t source_ref 写入质量 shadow 评估和 Phase 6u source_ref 扩展测试集，说明 shadow-only 边界、候选识别率、candidate precision、关键记忆误伤率、真实回源可信度和第三张主表接入方式。

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
- Phase 6b-4：证据使用 debug 和真实 LLM 基线/增强对照。新增 `--case-id`、`--repeat-count`、`--evidence-prompt-mode baseline|coached|both` 和 `--include-answer-debug`，常规报告仍脱敏，完整回答和证据块只写入临时 workspace 的 `answer_debug`。本轮真实 LLM 对 `vague_reference_graph` 跑 5 轮 baseline + 5 轮 coached，10/10 通过。
- Phase 6c-1：离线 uplift report，复用 Phase 6a fixture 和 profile 对照，把 Phase 2-5 的 shadow trace 转成离线 proxy uplift。它不调用真实 LLM、不读真实 memory DB，也不声明生产性能提升；第一版输出 phase summary、feature records、overall_avg_uplift、positive/negative diagnostic signals、token delta 和 estimated token saving。
- Phase 6d：量化 uplift 总表，基于 80 个目标导向 case（common 40 / hard 40）把 `memory_base`、单项开关和 `all_on` 放到同一张表里，`off` 只作为关闭增强控制组。当前报表路径是 `my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.json` 和 `memory_quantitative_uplift_eval.md`；本轮离线结果里，`baseline_main_score = 94.375`、`all_on_main_score = 69.5543`、`total_uplift_points = -24.8207`，`common_main_score = 69.067`、`hard_main_score = 70.1364`，单项 uplift 里三路召回最高，`tri_retrieval_only = 87.4997`，其后是图谱召回、重排与注入治理、版本链与溯源、写入价值、睡眠巩固。token 相关输出改为 `token_signal_kind/value/delta`，组合态混合成本和节省信号时标记为 `mixed`，不再硬拼总 token 数。
- Phase 6d-chain：链路量化评测，基于同一批 80 个目标导向 case 输出 `chain_memory_base -> chain_write_value -> chain_tri_retrieval -> chain_graph_retrieval -> chain_rerank_injection -> chain_version_provenance -> chain_sleep_consolidation -> chain_all_on` 的累计链路分数，`chain_off` 只作为关闭增强控制组。报表路径是 `my_md/memory_optimization/eval_reports/memory_quantitative_chain_eval.json` 和 `memory_quantitative_chain_eval.md`；当前离线结果里，最终主分从 `94.375` 到 `69.5543`，总提升 `-24.8207` 分。相邻增益最高的是 `chain_write_value`，`-40.4156` 分后的继续打开三路召回开始回升；`chain_tri_retrieval` 继续提升 `+18.2433` 分；`chain_graph_retrieval` 小幅下降 `-0.1093` 分；后续治理和睡眠步骤在当前平均评分公式下继续下降，说明组合权重和 active 化策略还需要优化，不能简单把所有能力平均打开。
- Phase 6d-balanced：分层 balanced 链路评测，继续使用同一批 80 个目标导向 case，把回答、召回代理、证据、治理和效率分开计分。报表路径是 `my_md/memory_optimization/eval_reports/memory_quantitative_balanced_eval.json` 和 `memory_quantitative_balanced_eval.md`；当前离线结果里，`baseline_balanced_score = 12.6923`、`final_balanced_score = 67.2022`、`total_balanced_uplift_points = 54.5099`，common 最终分 `66.6972`，hard 最终分 `67.7072`。Balanced report 借鉴 RAG/Agent 分层评测共识，把回答、召回代理、证据、治理和效率分开；本项目的改进是把 memory 生命周期治理纳入评分，包括 forbidden、source_ref、版本链、scope 隔离和 token/sleep 信号。它仍然是离线代理评测，不是生产回答准确率。
- Phase 6d-layered：三层评分评测，把即时回答、写入治理和记忆库卫生分开看。报表路径是 `my_md/memory_optimization/eval_reports/memory_layered_scoring_eval.json` 和 `memory_layered_scoring_eval.md`；当前离线结果里，`baseline_total_layered_score = 94.375`、`final_total_layered_score = 54.9521`、`total_layered_uplift_points = -39.4229`，common 最终分 `54.773`、hard 最终分 `55.1312`，`chain_all_on` 的写入治理分 `49.3334`，记忆库卫生分 `35.4107`。这份报表专门用来说明写入和巩固不应只按回答分评价。
- Phase 6f-target-metrics：下一步把三层分数继续拆成三组目标百分比指标。回答效果组评估三路召回、图谱召回、重排注入治理和版本链溯源；写入治理组只评估写入价值治理；记忆库卫生组评估睡眠巩固、层级溯源和版本链库级信号。这样可以用“目标记忆召回率从 A% 到 B%”“污染写入拦截率从 A% 到 B%”“重复合并率达到 A% / token 节省 B%”这类表达替代笼统的综合分。详细设计见 [05-memory-target-metric-eval-plan.md](./05-memory-target-metric-eval-plan.md)。
- Phase 6h-target-metrics：继续修订目标指标口径。当前正式报告仍是 `my_md/memory_optimization/eval_reports/memory_target_metrics_eval.json` 和 `memory_target_metrics_eval.md`，`measurement_mode = offline_trace_real_baseline_target_metrics`，`online_status = gated_no_checkpoint`。80 case 结果显示：三路召回目标召回率 `93.75% -> 100%`，图谱召回按 graph 专用目标分母修订为 `97.5% -> 100%`，重排与注入治理 `93.75% -> 100%`，版本链与溯源 `90% -> 100%`；hard 子集分别为三路 `87.5% -> 100%`、图谱 `95% -> 100%`、版本链当前有效版本 `80% -> 100%`。版本链新增 forked replacement-chain fixture 后，`conflict_chain_detection_rate.after = 100%`。这些仍是离线 shadow / proxy 指标，不代表生产准确率或真实 LLM 线上效果。
- Phase 6i-evidence-input：补强写入治理和记忆库卫生的线上 evidence 输入边界。`scripts/run_memory_target_metrics_eval.py` 现在支持 JSON 数组、`{"records": [...]}` 和 JSONL evidence，并会拒绝缺字段、非法 label / decision / state、字符串布尔值、负数或非数字 token 估算。这个阶段只保证 evidence 入口可信，不代表真实 evidence 已经采集完成。
- Phase 6j-comprehensive-case-pack：新增显式 `--case-pack comprehensive` 完整目标导向测评集，不改变默认 80 case 标准集。完整集规模为 320 case，其中 common 160、hard 160，覆盖 20 类场景、8 个变体、960 个写入候选和 2400 个记忆库卫生扫描单元。`scripts/run_memory_target_metrics_eval.py --case-pack comprehensive` 已在 `/tmp/akashic-memory-comprehensive-pack` 跑通离线 smoke：三路召回 `98.125% -> 100%`，图谱召回 `98.75% -> 100%`，重排与注入治理 `98.125% -> 100%`，版本链与溯源 `97.5% -> 100%`，写入价值治理污染拦截率 after `100%`，睡眠巩固 token 节省率 after `32.8125%`。这仍是离线代理结果，不是正式线上 LLM 结论。
- Phase 6k-real-llm-core-eval：真实 LLM 核心矩阵已完成，使用 `--checkpoint-jsonl /tmp/akashic-memory-phase6k-real/reports/memory_comprehensive_online_eval.checkpoint.jsonl --resume` 从 325 条 checkpoint 继续补齐到 `case_count = 1280`。最终真实报告是 `/tmp/akashic-memory-phase6k-real/reports/memory_comprehensive_online_eval.json` 和 `.md`；checkpoint 重建版是 `/tmp/akashic-memory-phase6k-real/checkpoint-report/memory_comprehensive_online_eval.json` 和 `.md`。最终结果为 `unique_case_count = 320`、`profile_count = 4`、`prompt_variant_count = 1`、`repeat_count = 1`、`answer_rule_pass_rate = 23.9844`、`memory_grounding_pass_rate = 75.0`、`forbidden_violation_rate = 15.7812`、`total_token_count = 6971048`、`avg_latency_ms = 4639.9172`。这仍然只覆盖 answer/retrieval 核心矩阵，不包含写入治理和睡眠巩固的真实 evidence。
- Phase 6l-baseline-plus-count：320 case comprehensive 离线计数评测已完成，详细见 [06-memory-320-baseline-plus-count-eval.md](./06-memory-320-baseline-plus-count-eval.md)。原始记忆基线命中 `628/640`、召回率 `98.12%`；三路召回提升到 `640/640`，多命中 12 条，召回率提升 `+1.88` 个百分点；图谱召回提升到 `638/640`，多命中 10 条，召回率提升 `+1.57` 个百分点。全开组合为 `370/640`，低于原始记忆基线，说明后续不能简单全开，需要场景路由和分层评测。
- Phase 6m-answer-comprehensive-v2：新增 answer/retrieval-only 扩展测试集，正式报告见 `my_md/memory_optimization/eval_reports/memory_answer_retrieval_counts_eval.json` 和 `.md`。本轮离线 deterministic 结果基于 `1000 case / 2000 target`：原始记忆基线命中 `1978/2000`，三路召回命中 `2000/2000`，图谱召回命中 `1994/2000`，纯回答组合链路到重排注入保持 `2000/2000`，版本链与溯源后为 `1998/2000`，回答链路全开为 `1998/2000`。写入治理和睡眠巩固已从这张回答主表的行和底层 feature 中排除。
- Phase 6n-write-governance：新增并调优写入治理离线计数评测，详细见 [07-memory-write-governance-count-eval.md](./07-memory-write-governance-count-eval.md)。本轮基于 `1200` 个目标导向模板候选，构成为 common `600`、hard `600`，6 类各 `200` 条；原本写入方式写入 `1200/1200`，其中有用候选 `400/400` 不会漏写，但污染、重复和冲突候选也会写入 `800/800`。叠加写入价值治理后直接写入 `172/1200`，写入减少率 `85.6667%`，污染候选第一阶段控制率 `97.25%`。调优后直接拒绝误伤率从 `20.0%` 降到 `0.0%`，冲突复核缺口率从 `71.0%` 降到 `0.0%`；有用候选直接保留率仍为 `37.5%`，hard 有用候选主要进入 review。随后新增离线 `review resolver`、最终写入安全门和 hard useful recovery 调优：复核候选 `503` 条，复核后晋升写入 `253` 条，最终写入 `400/1200`，有用候选最终保留率 `100.0%`，hard 有用候选最终保留率 `100.0%`，最终污染控制率 `100.0%`，冲突复核保持率 `100.0%`，hard 重复泄漏率 `0.0%`。相对严格理想状态的差距总数从 `54` 降到 `0`。该阶段仍是离线 shadow 评测，没有改变线上 AgentLoop 或真实写入行为；要转成线上结论，还需要真实候选、真实决策、真实写入结果和后续召回有用率 evidence。
- Phase 6o-write-governance-online-shadow：新增 `scripts/run_memory_write_governance_online_eval.py`，把测试集候选穿过真实 `AgentLoop.process_direct()` 并生成 `memory_write_governance_online_evidence.jsonl`，再接入 `scripts/run_memory_target_metrics_eval.py --online-write-evidence-json`。fake-provider smoke 使用 `1200` 个候选跑通全量路径，`infra_passed = True`，`total_token_count = 36000`；真实 LLM pilot 使用 `24` 个候选跑通链路。随后修复有限样本选择逻辑，让 `--case-set all --limit 240` 同时按 common/hard 和 6 类分层抽样，并完成 `240` 条真实 LLM 扩展样本：common `120`、hard `120`，6 类各 `40`，`infra_passed = True`，`provider_error_count = 0`，`timeout_count = 0`，`total_token_count = 1236228`，`avg_latency_ms = 2366.625`。真实扩展 evidence 分布为 useful `80` 全部 allow、pollution `80` 全部 reject、duplicate `40` 全部 reject、conflict `40` 全部 review；target metrics 线上 evidence 行显示：有效写入精度 `33.3333% -> 100.0%`，污染拦截率 `0.0% -> 100.0%`，重复控制率 `0.0% -> 100.0%`，冲突复核率 `0.0% -> 100.0%`，写入减少率 `0.0% -> 66.6667%`，误拒率保持 `0.0%`，误收率 `100.0% -> 0.0%`。这仍是测试集驱动的线上 shadow 验证，不代表生产流量，也不代表 LLM 自动抽取候选记忆的质量。
- Phase 6p-sleep-hygiene-evidence：新增 `scripts/run_memory_sleep_hygiene_evidence_eval.py`，把目标导向睡眠巩固快照穿过现有 `sleep_consolidation_shadow`，生成 `online_hygiene_records` 兼容 evidence，并输出第三张主表可消费的 target metric 报告。默认 600 case 扫描 750 条 active item，evidence row `600`；重复候选识别率 `100.0%`，过期候选识别率 `100.0%`，低价值候选识别率 `100.0%`，来源覆盖率 `90.0%`，proxy 回源成功率 `100.0%`，shadow 估算 token 节省率 `64.0138%`，关键记忆保持率 `100.0%`，关键记忆误伤候选数 `0`，非预期候选数 `0`，误伤候选率 `0.0%`，实际应用变更数 `0`。这仍是离线 evidence / shadow-only 评测，不代表真实 DB 已清理或真实 prompt token 已下降。
- Phase 6q-sleep-hygiene-hard-eval：新增 hard / adversarial 睡眠巩固评测，输出 standard / hard / overall 三组结果，用 candidate recall、candidate precision、retained protection 和 false positive cleanup 替代单纯 100% 候选命中表达。正式 V2 报告为 `920` case、`1120` evidence rows：standard candidate precision `100.0%`、hard candidate precision `75.0%`、overall candidate precision `93.4426%`；hard retained protection `90.0%`，false positive cleanup `10.0%`，safe evidence token saving 为 `unsafe`。target metrics 仍保留单行 online hygiene evidence，hard split 在 dedicated report 中展示。
- Phase 6r-sleep-hygiene-safety-v3：新增 V3 安全候选口径和 non-mutating dry-run patch。正式报告位于 `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence_v3/`，把 `cleanup candidate` 和 `merge suggestion` 分开，near-merge 只进入 review，不计入安全清理。当前 V3 overall 为 `920` case、`1120` rows，cleanup recall `100.0%`，cleanup precision `100.0%`，retained protection `100.0%`，false positive cleanup `0.0%`，merge suggestions `40`，review required `120`，safe cleanup token saving `42.5121%`。新增 evaluator 侧 `source_ref` resolver，formal synthetic run 仍使用 `source_fetch_mode = proxy`；session-store 回源只在 fixture 或真实 `sessions.db` 模式下使用。dry-run patch 只输出拟动作和恢复性状态，`writes_real_db = false`。
- Phase 6s-sleep-hygiene-source-backed：新增 source-backed fixture、源证据聚合指标和 patch 来源安全门。正式报告位于 `my_md/memory_optimization/eval_reports/sleep_hygiene_source_backed_v1/`，使用 fixture `sessions.db` 和真实 `SessionStore.fetch_by_ids()` 验证消息 ID 回源。当前结果为 `160` case、`200` evidence rows，source_ref 覆盖率 `81.5%`、解析成功率 `82.2086%`、真实回源成功率 `36.1963%`、原文支持率 `18.4049%`；`200` 条 patch 记录中只有 `12` 条满足 `source_backed_action_safe`。这仍是 fixture / shadow-only，不写真实 memory DB，不开启 active cleanup。
- Phase 6t-source-ref-quality-shadow：新增 `memory2/source_ref_quality.py`、`memory2/eval_source_ref_quality.py` 和 `scripts/run_memory_source_ref_quality_eval.py`，专门评估写入阶段如果能携带当前会话消息级 `message_id`，能否把 session 级、缺失或 malformed 的 `source_ref` 在 shadow 报告中规范成消息级来源。正式报告位于 `my_md/memory_optimization/eval_reports/source_ref_quality_shadow_v1/`；当前 6 个 synthetic controlled fixture 候选中，message-level 覆盖率 `33.3333% -> 83.3333%`，解析成功率 `66.6667% -> 100.0%`，真实回源成功率 `33.3333% -> 83.3333%`，原文支持率 `16.6667% -> 66.6667%`，source-backed eligible `1/6 -> 4/6`。这不是生产线上提升，不写真实 `memory_items.source_ref`，不打开未标记的生产 `sessions.db`。
- Phase 6u-source-ref-quality-expanded：新增 `memory2/eval_source_ref_quality_cases.py`，并扩展 `scripts/run_memory_source_ref_quality_eval.py --case-pack expanded`。正式报告位于 `my_md/memory_optimization/eval_reports/source_ref_quality_expanded_v1/`；当前 `200` 条目标导向 synthetic fixture 中，message-level 覆盖率 `40.0% -> 90.0%`，解析成功率 `80.0% -> 100.0%`，真实回源成功率 `20.0% -> 80.0%`，原文支持率 `10.0% -> 70.0%`，source-backed eligible `20/200 -> 140/200`。common 组 after eligible `80.0%`，hard 组 after eligible `60.0%`；hard 组保留 foreign-only、missing message 和 unsupported source 等应阻断场景。这仍是测试集驱动 shadow 结论，不代表生产自然流量。
- Phase 6e：综合线上 answer-level 评测。新增 `memory2/eval_comprehensive_online.py` 和 `scripts/run_memory_comprehensive_online_eval.py`，用真实 `AgentLoop.process_direct()`、真实 LLM、受控 memory engine、80 个目标导向 case、8 个链路 profile、2 个提示词变体、2 次 repeat 设计完整 `2560` run。真实运行到 `checkpoint_input_count = 1599` 时，外部 provider 返回 `402 Insufficient Balance`，按计划停止；排除 timeout / provider error 后生成部分真实报告，`case_count = 1417`、`unique_case_count = 45`、`excluded_infra_failure_count = 182`、`total_token_count = 7600606`、`infra_passed = True`、`answer_quality_passed = False`。报表路径是 `my_md/memory_optimization/eval_reports/memory_comprehensive_online_eval.json` 和 `.md`。这份报告只能说明余额耗尽前 1417 条有效真实调用的 answer-level 行为，不能当作完整 2560-run 结论；脚本退出码 0 只表示有效样本报告生成成功，不表示答案质量全通过。

Phase 6e 的主要可量化结论：

- 关闭记忆链路 `chain_off`：`main_score = 18.4269`，`answer_rule_pass_rate = 12.9213`，`memory_grounding_pass_rate = 0`。
- 只开写入价值 `chain_write_value`：相对关闭 `-0.3478`，符合预期；写入价值不直接给当前回答注入证据，它的价值应主要看离线写入质量和污染率。
- 打开三路召回 `chain_tri_retrieval`：相对关闭 `+35.5279`，是本轮 answer-level 最大基础增益来源。
- 增加图谱召回 `chain_graph_retrieval`：相对关闭 `+36.4319`，相邻 `+0.904`，在当前已完成样本里是小幅正增益。
- 增加重排和注入治理 `chain_rerank_injection`：相对关闭 `+43.155`，相邻 `+6.7231`，是本轮 answer-level 最强 profile。
- 增加版本链与溯源 `chain_version_provenance`：相对关闭 `+23.946`，但相邻 `-19.209`，因为当前 profile 的 memory grounding 为 `0`，说明此阶段证据 ID 显示和受控注入策略还需要修订。
- 增加睡眠巩固 `chain_sleep_consolidation`：相对关闭 `+28.5788`，相邻 `+4.6328`；它在 balanced proxy 中相邻 `+14.4267`，说明治理、证据和效率维度能体现部分价值。
- 全开 `chain_all_on`：相对关闭 `+26.9968`，相邻 `-1.582`；当前不能简单宣称“全开最好”，更合理的 active 化顺序是先验证三路召回、图谱召回、重排注入治理，再处理版本链和睡眠巩固的组合策略。

写入价值和睡眠巩固的评测口径需要单独看：

- 写入价值的核心作用是“少写错、少写脏、少写重复、保留真正长期有用的信息”，不是让当前这一轮回答马上变好。它更适合用写入治理指标评测：`policy_allow_count`、`policy_reject_count`、`temporary_reject_count`、`assistant_inference_reject_count`、`duplicate_risk_count`、`write_reduction_rate`、`memory_pollution_rate`、`useful_memory_precision` 和后续多轮里的 `future_recall_usefulness`。
- 睡眠巩固的核心作用是“长期记忆库维护”，不是即时问答增强。它更适合用库级和检索级指标评测：`duplicate_group_count`、`merge_candidate_count`、`stale_candidate_count`、`low_value_candidate_count`、`conflict_candidate_count`、`estimated_token_saving`、`estimated_redundancy_drop`、巩固前后 active 记忆数量、检索 precision、错误召回率、prompt token 变化和关键记忆保护率。
- 所以后续评测不应只用 `answer_rule_pass_rate` 给这两个能力下结论。更合理的方式是把总评测拆成三层：当前回答层评测三路召回、图谱召回、重排注入治理；写入治理层评测写入价值；记忆库卫生层评测睡眠巩固。最后再用 balanced score 或按场景加权的综合分汇总。

后续还有 3 个主要方向：

1. 写入治理：1200 候选离线计数已补齐“有用候选最终保留率”和误拒控制；下一步要补真实线上候选 evidence 和后续召回有用率，避免只用离线模板结果代表生产效果。
2. 记忆库卫生：补真实 evidence 输入，包括巩固前后 active 数、真实 prompt token、关键记忆保护率。
3. Phase 6e checkpoint 转换与续跑：先用已有 checkpoint 重建新版目标指标表；如果 provider 余额恢复，再用同一个 checkpoint `--resume` 补齐完整 `2560` run。
4. Phase 6 后续：在离线指标可解释、真实 LLM 评测稳定后，继续补 Dashboard 展示、连续评测和 active 化决策。

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
- 真实 LLM 人工确认运行结论：本轮使用主 checkout 的 `config.toml` 跑通真实 provider，`real_llm_enabled = True`，没有 provider error，也没有 timeout。3 个 case 中 `preference_recall` 通过，`cross_scope_isolation` 和 `vague_reference_graph` 因固定关键词缺失未通过；但 `expected_memory_used_count = 3`，说明受控 memory id 注入和记录链路是通的。当前失败更像答案规则过窄，而不是记忆未召回。
- 真实 LLM 本轮指标：`case_count = 3`、`passed_case_count = 1`、`failed_case_count = 2`、`answer_contains_pass_count = 3`、`answer_contains_miss_count = 2`、`expected_memory_used_count = 3`、`provider_error_count = 0`、`timeout_count = 0`、`token_metrics_available = True`、`total_token_count = 14911`、`total_latency_ms = 10114`、`avg_latency_ms = 3371`。
- 后续需要修订：答案期望应支持同义词 / 任一命中组，避免把“Telegram”“三路召回”这类表达方式当成唯一正确表述；token usage 解析也需要兼容 provider 只返回 prompt/total 或 input/output 字段的情况。
- 修订后真实 LLM 复测结论：答案评分器已支持“必须命中项 + 同义词任一命中组”，`LLMProvider` 已把标准 usage 写入 `provider_fields["usage"]`，所以 completion token 可以记录。复测结果为 `case_count = 3`、`passed_case_count = 2`、`failed_case_count = 1`、`memory_grounding_pass_count = 3`、`answer_rule_pass_count = 2`、`completion_token_count = 602`、`total_token_count = 17098`。仍失败的 `vague_reference_graph` 缺少 `RRF` 和第三路相关同义词，说明该 case 当前暴露的是模型未稳定使用具体排序证据，而不只是评分规则过窄。

当前存在的问题：

- `vague_reference_graph` 仍未通过。报告显示期望 memory id 已命中，但最终回答没有出现 `RRF` 或“第三路 / 三路召回 / 融合排序”相关表达。
- 真实 LLM 样本仍然很小，当前只有 3 个 case，不能代表整体长期记忆质量。
- 本阶段 memory 数据仍是 fixture 受控数据，不是真实 `workspace/memory/memory2.db`，所以还不能说明真实用户记忆库上的召回和回答效果。
- 当前答案评分仍以关键词和同义词组为主，尚不能覆盖所有语义等价表达，也不能证明 source support 完整可靠。

可能原因：

- 记忆虽然被检索并注入，但 prompt 中没有强约束模型必须使用或复述关键证据，导致模型可能给出泛化回答。
- `vague_reference_graph` 是模糊指代场景，问题短、上下文依赖强，模型可能没有把“第三路方案”稳定映射到 `RRF 融合排序` 这条记忆。
- 受控 memory engine 只保证注入 memory summary，并不模拟真实三路召回、图谱路径、source_ref 回源后的证据强化。
- 答案评测没有保存完整回答正文，隐私边界更安全，但排查语义等价失败时可观测性较弱；后续可增加显式手动开关，把答案 debug 写到临时目录且不提交。

Phase 6b-4 的验证结论：

- 新增证据使用 debug 开关，只有显式传入 `--include-answer-debug` 时才把完整回答和注入证据块写到 `<workspace>/answer_debug/`，不会写入 `my_md` 常规报告。
- 新增 `--evidence-prompt-mode baseline|coached|both`。`baseline` 保持原记忆块，`coached` 只在 eval-only memory engine 中加入“优先使用记忆并保留关键术语”的提示，`both` 用于同一 case 的对照实验。
- 新增重复评测指标：`repeat_count`、`repeat_pass_rate`、`repeat_answer_rule_pass_rate`、`repeat_memory_grounding_pass_rate`，以及按 `prompt_variant` 拆分的通过数。
- focused tests：`tests/test_memory_eval_llm_sample.py` 为 `16 passed`，`tests/test_memory_llm_sample_cli.py` 为 `9 passed`。
- fake-provider smoke：`vague_reference_graph` 在 `repeat_count = 2`、`prompt_variant_mode = both` 下生成 4 条 case record，并成功写出本地 debug 文件。
- 真实 LLM 对照：`case_count = 10`、`repeat_count = 5`、`passed_case_count = 10`、`failed_case_count = 0`、`answer_rule_pass_count = 10`、`memory_grounding_pass_count = 10`。
- 按变体拆分：`pass_count_by_prompt_variant = {'baseline': 5, 'coached': 5}`、`answer_rule_pass_count_by_prompt_variant = {'baseline': 5, 'coached': 5}`、`memory_grounding_pass_count_by_prompt_variant = {'baseline': 5, 'coached': 5}`。
- 真实 LLM token/延迟：`prompt_token_count = 49865`、`completion_token_count = 2697`、`total_token_count = 52562`、`total_latency_ms = 46977`、`avg_latency_ms = 4697`。
- 本轮结论：上一轮失败的 `vague_reference_graph` 在 10 次真实调用中都命中了 `RRF` 和第三路相关表达。debug 摘要显示 baseline 本身也能通过，因此本轮不能证明 coached 提示显著优于 baseline，只能说明“证据使用失败”不是稳定复现的问题，需要更大样本或更难 case 才能量化差异。

Phase 6c-1 的验证结论：

- 新增 `memory2/eval_uplift.py` 和 `scripts/run_memory_uplift_eval.py`。
- 报告路径：`my_md/memory_optimization/eval_reports/memory_uplift_eval.json` 和 `.md`。
- 当前报告是离线 fixture proxy uplift，不是真实生产 uplift。
- `llm_calls_enabled = false`、`embedding_calls_enabled = false`、`real_memory_db_enabled = false`、`production_uplift_claimed = false`。
- 记录 Phase 2-5/all 的 `avg_baseline_score`、`avg_experimental_score`、`avg_uplift`、positive/negative signal、token delta 和 estimated token saving。

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
