# 成本与时延观测

本文记录 akashic Agent 当前的成本/时延观测方式、测试结论和后续优化路线。目标不是让回答变短，而是在同等成功率下减少不必要的 token、降低延时，并让每一轮优化都有可对比的数据。

## 数据来源

运行时观测数据写入 `~/.akashic/workspace/observe/observe.db`。推荐通过状态命令查看：

```text
/usage_arch
/usage_tag <tag>
/usage_profile [profile]
/usage_experiments
/usage_baseline [N]
/usage_compare <tag_a> <tag_b>
/usage_turn <id>
```

指标可信度按优先级理解：

- `actual_*`：模型厂商返回的 usage，作为成本结论的主要依据。
- `cache_hit/miss`：从厂商 usage 或兼容字段提取，受厂商返回字段影响。
- `estimated_*`：本地估算，只用于辅助定位，不作为最终成本结论。
- `turn_duration_ms` / `llm_duration_ms_sum` / `tool_duration_ms_sum`：用于区分慢在模型、工具还是整体链路。

## Profile 控制

优化实验通过 profile 切换，不需要改代码。默认配置建议保持保守：

```toml
[agent.optimization]
enabled = false
default_profile = "baseline"
```

开启后，当前内置 profile：

| profile | 行为 |
| --- | --- |
| `baseline` | 关闭全部优化，使用原始 memory window、完整工具 schema 和完整工具结果。 |
| `simple_fast_path` | 仅对明确简单、无工具意图的问题启用轻量路径。 |
| `context20` | 将本轮 history/memory window 设为 20。 |
| `context12` | 将本轮 history/memory window 设为 12。 |
| `tool_result_limit` | 限制进入下一次 LLM 调用的单条工具结果长度。 |
| `combined_p1` | 同时启用 `simple_fast_path`、`context20`、`tool_result_limit`。 |

命令：

```text
/usage_profile
/usage_profile baseline
/usage_profile simple_fast_path
/usage_profile context20
/usage_profile context12
/usage_profile tool_result_limit
/usage_profile combined_p1
```

`/usage_profile <profile>` 只影响当前 session，并自动把 observe 的 `experiment_tag` 设为同名 profile。`/usage_tag <tag>` 仍可用于手动实验分组，手动 tag 的优先级高于 profile 默认 tag。

## Profile 框架实现记录

本次更新完成的是“可切换、可观测、可回退”的 profile 实验框架，不是新的线上性能 A/B 结论。它解决的问题是：后续对比不再靠临时改代码，而是通过 `/usage_profile` 在同一套主链路中切换行为。

实现内容：

- 新增 `agent.optimization` profile 解析模块，集中定义内置 profile。
- 新增 `[agent.optimization]` 配置，默认 `enabled=false`、`default_profile="baseline"`。
- `baseline` 明确关闭所有优化，用原始 memory window、完整工具 schema 和完整工具结果。
- `simple_fast_path` 只允许明确简单、无工具意图的问题走轻量路径。
- `context20` / `context12` 真实影响 before-turn context prepare、reasoner history 和 after-turn budget 统计。
- `tool_result_limit` 会在工具结果进入下一次 LLM 调用前截断单条长结果；原始工具执行和审计链路不因此绕过。
- `combined_p1` 叠加 `simple_fast_path`、`context20`、`tool_result_limit`。
- `/usage_profile [profile]` 支持当前 session 查看和切换，并同步写入 observe `experiment_tag`。
- `/usage_arch` 会显示 `optimization.enabled` 和 `optimization.default_profile`，方便排查 profile 未生效的原因。

测试验证：

| command | result |
| --- | --- |
| `uv run pytest tests/test_optimization_profiles.py tests/test_optimization_config.py tests/test_agent_core_p2_reasoner.py tests/test_lifecycle_phases.py::test_usage_command_compares_experiment_tags tests/test_lifecycle_phases.py::test_usage_compare_ignores_legacy_rows_without_actual_usage tests/test_bootstrap_wiring_p2.py::test_config_load_reads_memory_window_and_socket -q` | `34 passed` |
| `uv run pytest tests/test_agent_core_p5_agent_core.py tests/test_turn_pipelines.py tests/test_bootstrap_wiring_p2.py tests/test_observe_writer.py tests/test_lifecycle_phases.py -q` | `114 passed` |
| `uv run pytest -q` | `2799 passed, 3 skipped, 2 warnings in 315.76s` |
| `git diff --check` | passed |

当前结论：

- 代码层面已经具备 profile 切换和 observe 分组能力。
- 单元测试覆盖了 baseline 禁用优化、profile metadata 记录、session 隔离、memory window 覆盖、工具结果截断和 simple fast path 开关。
- 这次还没有产生新的真实成本/时延对比数据；下一步需要用相同问题集分别跑 `baseline`、`simple_fast_path`、`context20`、`tool_result_limit`、`combined_p1`，再用 `/usage_compare` 生成实际数据。

## 当前观察

最近一次小样本自测显示：

| tag | samples | avg prompt | avg total | avg turn | avg llm | avg iterations | cache hit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline` | 3 | 82,983 | 83,776 | 10,623ms | 10,273ms | 1.67 | 78.5% |
| `memory20` | 3 | 52,674 | 52,960 | 5,464ms | 5,118ms | 1.00 | 72.7% |
| `selftest_base` | 3 | 14,982 | 15,264 | 5,046ms | 4,774ms | 1.00 | 76.0% |
| `selftest_repeat` | 3 | 18,835 | 19,052 | 3,690ms | 3,500ms | 1.00 | 94.2% |

注意：`memory20` 是当时的实验标签，不等于已经确认修改了真实 `memory_window` 配置。后续正式对比应使用 `memory20_real`、`memory12_real` 这类明确标签。

当前结论：

- 简单无工具请求仍会消耗较多 prompt tokens。
- 厂商 usage 明显高于本地估算，因为它包含 system prompt、工具 schema、上下文等完整请求体。
- cache hit rate 对延时影响明显；重复场景可能 token 更多但延时更低。
- 当前工具执行耗时不是主要瓶颈，主要成本来自 LLM 输入规模。

## P0 真实 A/B

P0 验证使用临时 workspace 和 in-process `CoreRuntime` 执行，避免影响正在运行的 QQBot、CLI、dashboard 和默认 workspace。测试直接调用 `AgentLoop.process_direct()`，仍走完整被动回复主链：会话、记忆检索、prompt render、reasoner、after turn、observe 落库都会执行。

测试方法：

- `baseline_off`：临时关闭 simple fast path，用相同简单问题模拟优化前线路。
- `simple_fast_path`：启用 simple fast path。
- 每组 3 条相同类型问题。
- `turn_metadata={"skip_post_memory": True}`，避免测试消息触发后置记忆写入。
- 使用厂商返回的 `actual_*` usage 和 observe DB 作为统计依据。

测试问题：

```text
不用工具，一句话回答：你是谁？
不用工具，简单解释一下 token 成本是什么。
一句话说明 memory_window 是什么。
```

线路验证：

| tag | tools | max_tokens | disable_thinking | tool_choice | simple_fast_path |
| --- | ---: | ---: | --- | --- | ---: |
| `baseline_off` | 18 | 8192 | false | auto | 0/3 |
| `simple_fast_path` | 0 | 1024 | true | 未传 | 3/3 |

数据结果：

| metric | baseline_off | simple_fast_path | delta |
| --- | ---: | ---: | ---: |
| samples | 3 | 3 | - |
| avg prompt tokens | 12,923.3 | 5,637.7 | -56.4% |
| avg completion tokens | 82.7 | 30.7 | -62.9% |
| avg total tokens | 13,006.0 | 5,668.3 | -56.4% |
| avg turn latency | 2,515.7ms | 1,811.7ms | -28.0% |
| avg LLM latency | 2,309.0ms | 1,605.0ms | -30.5% |
| tool duration | 0.0ms | 0.0ms | 0.0% |
| avg ReAct iterations | 1.0 | 1.0 | 0.0% |
| tool errors | 0 | 0 | 0 |
| cache hit rate | 67.0% | 64.3% | -2.7pt |

本轮发现并修复了一个真实链路问题：prompt render 会在用户消息前注入 `[当前消息时间: ...]` 时间锚点，导致简单消息长度超过 fast path 的 160 字符限制。现在 fast path 判定会先剥离该时间锚点，再判断用户原文。

P0 结论：

- simple fast path 线路正确：明确简单任务不再传工具 schema。
- 成本下降主要来自 `tools=18` 变为 `tools=0`，并同时降低 `max_tokens`、关闭 thinking。
- 小样本下 total tokens 下降约 56.4%，turn latency 下降约 28.0%。
- 本轮无工具错误，且被排除的链接/收藏类测试不会误入 fast path。
- 延时受模型服务波动影响，token 数据更稳定；后续阶段仍以 actual usage 作为主要判断依据。

## Profile 真实 LLM A/B v1

本轮验证的目标是比较内置 optimization profile 的真实厂商 usage、端到端时延和基础正确性。测试使用临时 workspace 和 in-process `CoreRuntime`，只在内存中开启：

```python
cfg.optimization.enabled = True
cfg.optimization.default_profile = "baseline"
cfg.peer_agents = []
cfg.proactive.enabled = False
cfg.memory_optimizer_enabled = False
cfg.wiring.toolsets = [name for name in cfg.wiring.toolsets if name != "mcp"]
```

本轮没有修改 `config.toml`，也没有写入默认 workspace。每个 profile 使用 5 条简单被动问题，共 25 次真实 LLM 调用；每轮设置 `skip_post_memory=True`，避免测试消息触发后置记忆写入。

测试问题：

```text
不用工具，一句话回答：你是谁？
一句话说明 memory_window 是什么。
简单解释一下 token 成本是什么。
不用工具，用一句话说明后台提醒在个人 AI 伙伴里的作用。
不用工具，概括一下这个项目当前优化 profile 的意义。
```

原始结果：

| profile | samples | usage | avg prompt | avg total | avg turn | avg llm | avg iter | errors | fast hits | cache hit | correctness |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `baseline` | 5 | 5 | 16,765.6 | 16,970.8 | 3,648.4ms | 3,407.0ms | 1.2 | 0 | 0 | 81.5% | PASS=5 WARN=0 FAIL=0 |
| `simple_fast_path` | 5 | 5 | 7,360.6 | 7,397.4 | 1,494.8ms | 1,252.8ms | 1.0 | 0 | 4 | 48.0% | PASS=5 WARN=0 FAIL=0 |
| `context20` | 5 | 5 | 13,293.8 | 13,409.0 | 2,317.4ms | 2,075.0ms | 1.0 | 0 | 0 | 85.9% | PASS=5 WARN=0 FAIL=0 |
| `tool_result_limit` | 5 | 5 | 13,351.0 | 13,545.4 | 3,087.6ms | 2,809.6ms | 1.0 | 0 | 0 | 86.1% | PASS=5 WARN=0 FAIL=0 |
| `combined_p1` | 5 | 5 | 7,358.2 | 7,390.0 | 1,753.6ms | 1,492.8ms | 1.0 | 0 | 4 | 59.5% | PASS=5 WARN=0 FAIL=0 |

相对 `baseline` 的变化：

| profile | prompt tokens | total tokens | turn latency | llm latency |
| --- | ---: | ---: | ---: | ---: |
| `simple_fast_path` | -56.10% | -56.41% | -59.03% | -63.23% |
| `context20` | -20.71% | -20.99% | -36.48% | -39.10% |
| `tool_result_limit` | -20.37% | -20.18% | -15.37% | -17.53% |
| `combined_p1` | -56.11% | -56.45% | -51.94% | -56.18% |

本轮结论：

- `simple_fast_path` 是当前最明确的第一阶段收益：在基础正确性不下降的小样本中，total tokens 下降约 56%，端到端时延下降约 59%。
- `combined_p1` 的 token 收益与 `simple_fast_path` 接近，但本轮时延略差于单独 fast path；后续应继续拆分确认是服务波动、上下文变化还是 profile 叠加成本。
- `context20` 对简单被动问题显示出约 21% token 降幅，但本轮问题没有深度考察长历史和记忆正确性，暂不建议直接作为默认策略。
- `tool_result_limit` 本轮没有真正压测长工具结果，因为测试问题都要求不用工具；因此这组数据不能证明工具结果治理有效，只能说明该 profile 在简单被动问题中没有出现明显错误。

限制和风险：

- `simple_fast_path` 和 `combined_p1` 的 fast path 命中是 4/5，不是 5/5。需要补充命中原因诊断或调整简单问题判定规则，再决定是否扩大覆盖。
- `baseline` 有两条回复出现审批提醒噪声，说明对话态或系统提醒可能影响质量标签；本轮正确性标签只能作为粗粒度 PASS/WARN/FAIL，不等价于严格人工评测。
- 本轮只覆盖简单被动问题，不覆盖工具任务、记忆召回任务和主动推送任务。正式启用 `combined_p1` 前，需要补一轮混合任务 A/B。

复盘索引：

| 项目 | 内容 |
| --- | --- |
| 测试方式 | 临时 workspace + in-process `CoreRuntime` + 真实 LLM 调用 |
| 测试范围 | 5 个 profile，5 条简单被动问题，合计 25 轮 |
| 关键保护 | 只在内存开启 optimization；关闭 peer agents、proactive、memory optimizer；移除 `mcp` toolset |
| 主要指标 | `actual_prompt_tokens_sum`、`actual_total_tokens_sum`、`turn_duration_ms`、`llm_duration_ms_sum`、`simple_fast_path`、`tool_error_count`、cache hit |
| 最佳结果 | `simple_fast_path`，相对 baseline 的 total tokens -56.41%，turn latency -59.03% |
| 可确认结论 | 简单无工具场景下，fast path 能稳定降本降时延且不降正确性 |
| 暂不下结论 | `tool_result_limit`、主动推送、工具任务、长历史记忆任务 |

## 后续测试大纲

后续测试的主线是：先确认优化不伤主链路正确性，再逐层扩大降本范围。每一阶段都应使用同一组 case、同一套 profile/tag 命名，并优先采用厂商返回的 `actual_*` usage 作为成本结论。

| 阶段 | 测试方向 | 主要问题 | 通过标准 | 输出 |
| --- | --- | --- | --- | --- |
| 1 | 混合任务 A/B | `simple_fast_path` 是否只命中简单任务，是否误伤工具、记忆、主动推送 | 简单任务 token/时延下降；工具、记忆、主动推送无 FAIL；工具错误为 0 | 混合任务 profile 对比表 |
| 2 | `context20` / `context12` | 压缩 history/memory window 后，长历史和记忆召回是否仍可靠 | token 下降明显；记忆类问题无关键事实丢失；回答不编造 | 上下文窗口收益/风险表 |
| 3 | `tool_result_limit` | 长工具结果进入 LLM 前截断后，是否仍能回答核心问题 | 长网页/长搜索/长内容库结果成本下降；回答能引用关键摘要；不因截断编造 | 工具结果治理压测表 |
| 4 | `combined_p1` | fast path、context window、tool result limit 叠加后是否稳定 | 成本接近单项最优；正确性不低于 baseline；无新增工具失败 | 组合 profile 复测结论 |
| 5 | 主动推送两阶段 | 后台轮询是否可以先轻量判断“值不值得推” | 无内容时少调用主模型；有重要内容时不漏推；跳过原因可记录 | 主动推送成本/漏推表 |
| 6 | cache 稳定性优化 | 固定 prompt、工具 schema、上下文注入顺序后，cache hit 是否更稳 | cache hit rate 提升或波动下降；首 token/LLM 时延更稳定 | cache 命中趋势表 |
| 7 | 诊断增强 | 用户是否能一眼看到慢在哪里、为什么跳过、为什么失败 | `/usage_*`、schedule/proactive 诊断能直接展示 run_count、next_run_at、last_result、skip reason | 用户可读诊断清单 |

建议执行顺序：

1. 先做阶段 1，确认当前已证明有效的 `simple_fast_path` 不会误伤真实主链路。
2. 再做阶段 2 和阶段 3，分别验证上下文层和工具结果层。
3. 阶段 4 只在阶段 1-3 都没有明显正确性回退后执行。
4. 阶段 5-7 面向长期运行体验和可排错性，可以在成本数据稳定后推进。

阶段 1 的推荐 case 集：

| 类别 | 数量 | 示例 |
| --- | ---: | --- |
| 简单无工具 | 5 | “不用工具，一句话回答：你是谁？” |
| 工具任务 | 5 | “保存这个内容链接并标记为 AI”；“搜索我保存过的装修内容” |
| 记忆任务 | 5 | “我之前说过我关注哪些内容方向？” |
| 主动推送任务 | 2 | “立即生成最近 24 小时内容回顾”；“查看每日回顾 schedule 状态” |

阶段 1 的最低验收线：

- `simple_fast_path` 只能命中简单无工具任务；`combined_p1` 留到阶段 4 再做组合验证。
- 工具任务、记忆任务、主动推送任务的成功率不能低于 `baseline`。
- 任一 profile 出现 FAIL，应先修正确性问题，再继续做成本叠加。
- 成本结论必须基于 `actual_total_tokens_sum`，估算 token 只用于辅助定位。

### 阶段 1 Dry/Fake Run 记录

本轮是阶段 1 的 dry/fake run，只验证混合任务 case、profile 分组、fast path 命中范围和报告链路，不使用真实 LLM，因此不作为真实 token/时延收益结论。

| 项目 | 结果 |
| --- | --- |
| profiles | `baseline`、`simple_fast_path` |
| case 数 | 17 |
| fake turn 数 | 34 |
| real LLM | false |
| 输出报告 | `my_md/optimization_profiles/stage1_fake/optimization_stage1_fake_ab.md` |
| 原始 JSON | `my_md/optimization_profiles/stage1_fake/optimization_stage1_fake_ab.json` |
| 通过状态 | 无 FAIL，工具错误为 0 |

profile 汇总：

| profile | turns | pass | warn | fail | fast hits | tool errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline` | 17 | 17 | 0 | 0 | 0 | 0 |
| `simple_fast_path` | 17 | 17 | 0 | 0 | 4 | 0 |

类别检查：

| category | turns | fast hits | tool errors |
| --- | ---: | ---: | ---: |
| `simple_no_tool` | 10 | 4 | 0 |
| `tool_task` | 10 | 0 | 0 |
| `memory_task` | 10 | 0 | 0 |
| `proactive_task` | 4 | 0 | 0 |

核心检查：

- `baseline` fast hits 为 0。
- `simple_fast_path` fast hits 为 4，且只命中明确安全的简单无工具 case。
- `simple_004` 包含“后台提醒”语义，虽然用户写了“不用工具”，但该词靠近主动推送链路；保守策略下不期望命中 fast path。
- 工具、记忆、主动推送 case 均未被 fake fast path 命中。
- WARN/FAIL 汇总路径有单元测试覆盖，但默认 dry/fake case 全部为 PASS。

下一步：阶段 1 可以进入真实 LLM mini run，用同一组 case 和 profile 获取可信 `actual_*` usage、真实时延和人工正确性标签。

### 阶段 1 Real LLM Gated A/B 记录

本轮使用真实 LLM 跑 `baseline` vs `simple_fast_path`，范围是同一组 17 条混合 case。runner 使用独立临时 workspace：每个 profile/case 都在 `<workspace>/<run_id>/<phase>/<profile>/<case_id>` 下启动独立 runtime，并从该 case 自己的 observe DB 精确读取 `actual_*` usage，避免 profile 之间相互污染。

测试命令：

```bash
uv run python scripts/run_optimization_real_ab.py \
  --phase A \
  --workspace /tmp/akashic-real-ab \
  --out-dir my_md/optimization_profiles/real_ab \
  --enable-real-llm
```

输出：

| 项目 | 路径 |
| --- | --- |
| Markdown | `my_md/optimization_profiles/real_ab/optimization_real_ab_phase_a.md` |
| JSON | `my_md/optimization_profiles/real_ab/optimization_real_ab_phase_a.json` |

门禁结果：

| gate | result |
| --- | --- |
| real turns | 34 |
| case count | 17 |
| run_id | `realab-20260804T103253814625Z` |
| gate_pass | true |
| FAIL | 0 |
| missing/zero usage | 0 |
| unexpected fast path | 0 |
| tool errors | 0 |

profile 汇总：

| profile | turns | pass | warn | fail | avg prompt | avg total | avg turn |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline` | 17 | 17 | 0 | 0 | 26,362.5 | 27,038.1 | 9,431.1ms |
| `simple_fast_path` | 17 | 17 | 0 | 0 | 22,443.6 | 23,064.3 | 9,101.9ms |

paired delta：

| profile | paired cases | total tokens | turn latency |
| --- | ---: | ---: | ---: |
| `simple_fast_path` | 17 | -14.70% | -3.49% |

过程修正：

- 第一次 Phase A 运行失败在 `simple_004`：该 case 预期 fast path，但实际未命中。
- 失败不是工具错误或 usage 缺失，而是评测预期过宽。
- 由于“后台提醒/主动推送”属于容易靠近主动链路的语义，保守策略下不应强行进入 simple fast path。
- 已将 `simple_004.expected_fast_path` 修正为 false，并重新跑完整 Phase A。

本轮结论：

- `simple_fast_path` 在混合任务中没有误伤工具、记忆、主动推送 case，阶段 1 correctness/routing gate 通过。
- 在混合任务全集上，token 收益比之前“纯简单任务小样本”更低，这是合理的：17 条 case 中只有 4 条明确安全简单任务会命中 fast path。
- 当前可确认的是“轻量路径路由安全且有净收益”；不能把 -14.7% 推广到所有业务场景。
- 后续 Phase B/C/D 已按 gated 流程执行；见下一节汇总。

### 阶段 1 Real LLM Gated A/B 全阶段汇总

本轮继续执行 Phase B/C/D。所有阶段均满足当前成本 gate：无 FAIL、无 missing/zero usage、无 unexpected fast path、无 `tool_error_count`。注意：这个 gate 主要验证成本数据和粗粒度路由，不等价于严格功能正确性。各阶段的 baseline 是在同阶段、同 case 子集上重新跑出来的，因此只应看阶段内 paired delta，不应跨阶段直接比较 baseline 绝对值。

| phase | profile | turns | gate | baseline avg total | profile avg total | total delta | baseline avg turn | profile avg turn | latency delta |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A | `simple_fast_path` | 34 | pass | 27,038.1 | 23,064.3 | -14.70% | 9,431.1ms | 9,101.9ms | -3.49% |
| B | `combined_p1` | 34 | pass | 22,722.3 | 21,728.4 | -4.37% | 7,848.4ms | 7,994.5ms | +1.86% |
| C | `context20` | 10 | pass | 35,018.8 | 44,358.4 | +26.67% | 14,311.8ms | 18,412.8ms | +28.65% |
| D | `tool_result_limit` | 10 | pass | 27,139.8 | 27,479.2 | +1.25% | 7,146.8ms | 7,773.2ms | +8.76% |

阶段结论：

- Phase A：`simple_fast_path` 是当前最值得保留的 P0 优化。它在混合任务中没有误伤工具、记忆、主动推送 case，并有 token/时延净收益。
- Phase B：`combined_p1` 虽然 gate 通过，但相对 baseline 只降 token 约 4.37%，时延反而增加约 1.86%。当前不建议把组合 profile 作为默认策略。
- Phase C：`context20` 在 5 条记忆 case 上 token 和时延都上升。原因可能是独立 workspace 中缺乏真实历史记忆、记忆检索链路波动、或 window 改动没有命中预期收益点；当前不应据此启用为默认优化。
- Phase D：`tool_result_limit` 没有体现收益。由于本轮没有长工具结果压测，不能证明工具结果截断的降本效果；并且日志复查发现普通工具 case 的功能正确性 gate 不够严格，见下方问题记录。

日志复查发现的问题：

| 问题 | 证据 | 影响 |
| --- | --- | --- |
| 当前 gate 不等价于严格功能正确性 | gate 只检查 `FAIL`、missing/zero usage、unexpected fast path、`tool_error_count` | 工具未执行、未注册工具被拒绝、模型泄露工具调用文本时，仍可能被粗粒度 PASS 放过 |
| `tool_001` 保存链接 case 没有真实执行目标工具 | 多个 phase/profile 中 `tool_001` 的 observe 显示 `tools=[]`，没有调用 `save_content_item` | 成本数据仍可读，但该 case 不能算功能成功；后续工具任务必须断言目标工具调用 |
| 部分回复泄露 DSML 工具调用文本 | Phase B/D 的 `tool_001` 回复中出现 `<｜｜DSML｜｜tool_calls>`、`invoke name=...`，但 observe 中没有真实 tool call | 说明 provider/tool-call 解析链路没有接住模型输出的工具意图，当前 correctness 标注过宽 |
| 评测 runner 禁用文件/网络工具后，模型仍尝试调用 | 多个 case 的 `tool_audit.db` 记录 `read_file` 被 `tool_invocation_unregistered_tool` 拒绝 | 模型收到失败反馈后继续绕路，增加 ReAct 轮数、token 和时延；这会污染 profile 成本对比 |
| `context20` 反向主要来自更多 ReAct 轮数和更多工具调用 | Phase C 中 `memory_003` 从 3 轮变 5 轮，`memory_004` 从 3 轮变 6 轮，并伴随多次 `recall_memory` / 被拒绝的 `read_file` | 当前空临时 workspace 的记忆 case 不适合证明 memory window 降本；需要真实多轮历史专项测试 |
| `tool_result_limit` 未测到核心能力 | Phase D 只是普通内容库工具 case，没有长工具结果进入下一轮 LLM | 只能说明本轮没有通过成本 gate 失败，不能证明长工具结果截断有效 |

下一步建议：

- 保留 `simple_fast_path`，继续扩大样本确认简单任务覆盖率。
- 暂缓默认启用 `combined_p1`、`context20`、`tool_result_limit`。
- 补强真实 A/B harness 的 case-level gate：工具任务必须校验目标工具是否执行，回复中不能出现原始工具调用标记，`tool_invocation_unregistered_tool` 应计入 WARN/FAIL。
- 对 `tool_result_limit` 单独设计长工具结果压力测试，例如长搜索结果、长文档结果、长内容库列表。
- 对 `context20` 单独设计有真实多轮历史和可判定事实的记忆测试，不再用空临时 workspace 直接判断收益。

已接入的 harness 修正：

- `Stage1Case` 增加 suite 和功能期望元数据：`expected_tools`、`forbidden_reply_patterns`、`required_reply_patterns`、`allow_in_cost_latency`。
- 默认真实 A/B runner 使用 `cost_latency` suite，只运行 `allow_in_cost_latency=true` 的 case。
- `tool_001` 保存链接 case 暂时标记为 `disabled_tool_policy` / `allow_in_cost_latency=false`，不再进入 token/latency 成本结论。
- `RealABRecord` 增加 `actual_tools`、`expected_tools`、`denied_tool_attempt_count`、`unregistered_tool_count`、`forbidden_reply_pattern_count`、`expected_tool_missing_count`。
- gate 已纳入 expected tool 缺失、denied tool attempt、unregistered tool、DSML/tool-call 原始文本泄露。
- runner 会从每个 case 的 `observe/observe.db` 提取真实工具链，从 `tool_audit/tool_audit.db` 统计 denied/unregistered 工具尝试。
- 后续重新跑真实 A/B 后，旧的“工具未执行但 PASS”的 case 会被标成 gate failure，而不会继续污染成本对比。

### 最新复测：cost_latency v2

本轮在前述修正后重新执行了 Phase A/B/C/D。当前 `cost_latency` 套件只保留成本主线所需的 case：

- `shell`、`task_output`、`task_stop`、`write_file`、`edit_file`、`message_push`、`memorize`、`forget_memory` 已从成本评测 runtime 中裁剪。
- `memory_*` case 的 prompt 统一限定为只基于记忆和历史消息，不查文件。
- `proactive_001` 改为只测内容库回顾链路，并要求优先调用 `list_recent_content_items(hours=24, for_push=true)`。
- `tool_005` 已移出 `cost_latency`，作为审批/审计展示样本保留在 `disabled_tool_policy`。
- `plugins/content_library` 的 `search_content_items` 兼容了 `recent_24h` / `last_24h` / `24h`。

测试方法：

```bash
uv run python scripts/run_optimization_real_ab.py \
  --phase A \
  --suite cost_latency \
  --workspace /tmp/akashic-real-ab \
  --out-dir my_md/optimization_profiles/real_ab \
  --enable-real-llm
```

Phase B/C/D 使用同一条命令，只替换 `--phase`。本轮使用真实 LLM，不是 fake run；每个 profile/case 使用独立 workspace，并从各自的 `observe/observe.db` 读取真实 usage。

输出文件：

| phase | JSON | Markdown |
| --- | --- | --- |
| A | `my_md/optimization_profiles/real_ab/optimization_real_ab_phase_a.json` | `my_md/optimization_profiles/real_ab/optimization_real_ab_phase_a.md` |
| B | `my_md/optimization_profiles/real_ab/optimization_real_ab_phase_b.json` | `my_md/optimization_profiles/real_ab/optimization_real_ab_phase_b.md` |
| C | `my_md/optimization_profiles/real_ab/optimization_real_ab_phase_c.json` | `my_md/optimization_profiles/real_ab/optimization_real_ab_phase_c.md` |
| D | `my_md/optimization_profiles/real_ab/optimization_real_ab_phase_d.json` | `my_md/optimization_profiles/real_ab/optimization_real_ab_phase_d.md` |

本轮 gate 检查：

- `actual_prompt_tokens_sum` 和 `actual_total_tokens_sum` 必须存在且大于 0。
- `simple_fast_path` 命中必须符合 case 预期。
- `expected_tools` 不得缺失。
- `tool_error_count` 必须为 0。
- `denied_tool_attempt_count` 和 `unregistered_tool_count` 必须为 0。
- 回复中不得泄露 DSML 或原始工具调用文本。

最新结果：

| phase | profile | turns | gate | total token delta | turn latency delta |
| --- | --- | ---: | --- | ---: | ---: |
| A | `simple_fast_path` | 15 | pass | -13.99% | -28.54% |
| B | `combined_p1` | 15 | pass | -10.72% | -16.67% |
| C | `context20` | 5 | pass | +0.44% | +6.58% |
| D | `tool_result_limit` | 3 | pass | +9.52% | -3.41% |

最新结论：

- `simple_fast_path` 仍然是当前最稳的 P0 优化，且在混合任务上有净收益。
- `combined_p1` 通过 gate，但收益低于单独 fast path，不适合作为默认策略。
- `context20` 在空记忆样本上没有体现出 token 收益。
- `tool_result_limit` 本轮样本过小，且结果不支持把它直接提升为默认优化。
- 当前更合理的主线仍是：先保 `simple_fast_path`，再继续补强真正长历史、长工具结果、主动推送高负载场景。

## 成本来源

一次普通被动回复的成本通常来自：

- system prompt：固定角色、规则、协议。
- history context：近期对话窗口。
- memory injection：长期记忆、近期上下文、召回结果。
- tool schema：可见工具定义，简单任务也可能承担固定 schema 成本。
- ReAct iterations：每多一次模型调用都会重复携带上下文。
- tool result feedback：工具结果回填给模型，长网页、长文件、长搜索结果会放大成本。
- proactive polling：主动推送轮询、候选筛选和推送生成。

## P0 优化方向

P0 只做低风险、可回退优化。

### 简单任务轻量化

对明确简单且无工具意图的消息走轻量路径：

- 不传工具 schema。
- `tools=[]`。
- `max_iterations=1`。
- `max_tokens=1024`。
- `disable_thinking=True`。
- 默认仍使用主模型；配置了 `[llm.fast]` 时可使用轻量模型。

命中示例：

```text
不用工具，一句话回答：你是谁？
简单解释一下 token 成本是什么。
一句话说明 memory_window 是什么。
```

必须排除：

- 链接、图片、文件。
- 内容收藏、内容搜索、主动推送、审批、schedule 命令。
- 搜索、读写文件、shell、记忆召回等工具意图。
- “我之前说过什么”“我收藏过什么”“帮我查一下”这类需要事实来源的问题。

### 工具 schema 成本治理

简单任务最大的问题不是工具执行慢，而是工具 schema 作为固定上下文进入请求。P0 的治理方式是：明确无工具任务不传 tools；不确定时保留完整主循环。

验收标准：

- 简单任务 total tokens 平均下降至少 30%。
- 简单任务平均 turn latency 下降至少 20%。
- 工具任务误伤率为 0。
- 内容收藏、审批、主动推送命令不受影响。

## P1 优化方向

P1 在 P0 数据合格后再做。

- 做真实 `memory_window` 实验：`baseline`、`memory20_real`、`memory12_real`。
- 历史上下文压缩：减少不必要近期对话进入主 prompt。
- 工具结果压缩：进入 LLM 的单条工具结果默认限制在较小范围，完整结果通过 id、路径或 sidecar 保留。
- 内容库、搜索、文档工具优先返回结构化摘要，而不是默认塞全文。

验收标准：

- 普通问答 prompt tokens 平均下降至少 20%。
- 记忆问题回答质量不明显下降。
- 工具任务成功率不低于 baseline。
- 工具结果截断不导致回答编造。

## P2 优化方向

P2 面向长期运行成本。

- 主动推送两阶段：先轻量判断是否值得推，再调用主模型生成推送内容。
- 每日 token 预算：主动推送和后台任务超预算时降级为跳过、短摘要或延后。
- cache 稳定性：固定系统提示结构、工具 schema 顺序和动态上下文注入位置。
- 诊断展示：让用户看到推送为什么发生、为什么跳过、消耗多少。

## 对比方法

每个阶段都使用相同测试集：

- 简单无工具问题 5 条。
- 工具任务 5 条。
- 记忆任务 5 条。
- 主动推送任务 2 条。

推荐流程：

```text
/usage_tag baseline
执行 baseline 测试集

/usage_tag simple_fast_path
执行同一组测试集

/usage_compare baseline simple_fast_path
/usage_experiments
/usage_turn <id>
```

如果成功率下降，回退对应优化，不继续叠加下一阶段。
