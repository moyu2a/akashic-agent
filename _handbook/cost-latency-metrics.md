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
