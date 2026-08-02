# Memory Answer Correctness Uplift History

本文梳理从早期真实 LLM 评测到 P6o-27 为提升回答正确率做过的主要修改、测试方法、核心数据和结论。

## 当前结论

当前最新的中等规模 system-path 结果来自 P6o-27 fresh guarded real run：

- P6o-27 本轮最佳是 `safe_version_replace_guided_with_retry_shadow`：`34/40 = 85.0%` answer，grounding `100.0%`，forbidden `0.0%`。
- 同轮 `safe_version_replace_guided` 为 `31/40 = 77.5%`，`safe_version_replace` 为 `26/40 = 65.0%`。
- 但跨轮次仍有波动：P6o-24 中 retry-shadow 为 `29/40 = 72.5%`，低于 guided 的 `80.0%`；因此当前只能称为中等规模正向信号，不能称为已稳定最佳。
- 主要瓶颈已经从召回和 grounding 转移到 answer layer：证据能召回、能注入、grounding 常为 `100.0%`，但模型仍会漏掉 required terms、同义词组或语言要求。
- 生产默认仍应保持 `off`。目前改动均为 eval/config/shadow 路径，不应直接打开 graph-all-on、真实 retry 或生产默认。

## P6o-25 Answer Contract And Scorer Calibration

### 修改内容

- 仅强化 `guided_retry_shadow` 的 Answer Candidate Contract：
  - 要求先直接回答用户问题。
  - 要求复述至少一个当前事实。
  - 禁止只输出确认词、元动作、澄清问题或非用户要求的代码块。
- 在 eval-only scorer 中增加白名单等价表达：
  - `冲突` / `矛盾`
  - `清理` / `清掉`
  - `中文回答` / `保持中文` / `中文继续`
  - 已从 raw debug 证据确认的跨会话、版本叶子短句等价表达。
- 没有修改 retrieval、graph、memory write、生产默认、真实 retry 或 raw report 字段。

### 测试方法与数据

#### Focused regression

| test | result |
| --- | --- |
| contract/scorer/post-check focused tests | `37 passed` |
| system-path CLI fake-provider test | `1 passed` |
| fake-provider gate | `12` rows，3 modes，contract generation `100%`，post-check shadow `100%`，infra error `0` |
| real pregate | `10` unique cases，3 modes，`30` rows |

Focused regression commands：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_memory_system_path_safe_version_contract.py tests/test_memory_eval_llm_sample.py tests/test_memory_answer_post_check.py -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_memory_system_path_safe_version_eval.py::test_system_path_safe_version_cli_supports_guided_retry_shadow_mode -q -p no:cacheprovider
```

#### Fake-provider gate

Command：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o25-fake-gate-workspace --out-dir /tmp/akashic-p6o25-fake-gate-report --fake-provider --balanced-small --common-limit 2 --hard-limit 2 --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow
```

Fake-provider gate 数据：

| criterion | observed |
| --- | ---: |
| report path | `/tmp/akashic-p6o25-fake-gate-report/system_path_safe_version_eval.json` |
| case_count | `12` |
| unique_case_count | `4` |
| provider_error_count | `0` |
| timeout_count | `0` |
| `safe_version_replace` contract generation | `100.0%` |
| `safe_version_replace_guided` contract generation | `100.0%` |
| `safe_version_replace_guided_with_retry_shadow` contract generation | `100.0%` |
| retry-shadow contract enabled | `100.0%` |
| post-check shadow enabled | `100.0%` |

Fake-provider gate 结论：只验证 wiring、report 字段和 shadow contract 标记，不用于判断 answer 质量；fake provider 固定回答不会命中 case anchor，因此 answer rate 不是质量信号。

#### Real pregate

Command：

```bash
.venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o25-real-pregate-workspace --out-dir /tmp/akashic-p6o25-real-pregate-report --config /home/jjh/git_work/akashic-agent/config.toml --enable-real-llm --case-pack standard --balanced-small --common-limit 5 --hard-limit 5 --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow --timeout-s 30 --checkpoint-jsonl /tmp/akashic-p6o25-real-pregate-report/checkpoint.jsonl --early-infra-abort-count 3 --early-infra-abort-rate 0.5
```

Real pregate gate 数据：

| criterion | observed |
| --- | ---: |
| report path | `/tmp/akashic-p6o25-real-pregate-report/system_path_safe_version_eval.json` |
| case pack | `standard` |
| slice | common `5` + hard `5` |
| modes | `3` |
| repeats | `1` |
| case_count | `30` |
| unique_case_count | `10` |
| provider_error_count | `0` |
| timeout_count | `0` |
| malformed_checkpoint_line_count | `0` |
| token_metrics_available | `true` |
| memory_grounding_pass_rate | `100.0%` |
| forbidden_violation_rate | `0.0%` |

Real pregate mode 数据：

| mode | answer | grounding | forbidden | avg tokens | avg latency | would retry |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `safe_version_replace` | `6/10 = 60.0%` | `100.0%` | `0.0%` | `5486.9` | `4315.1ms` | `0` |
| `safe_version_replace_guided` | `8/10 = 80.0%` | `100.0%` | `0.0%` | `5564.1` | `4278.3ms` | `0` |
| `safe_version_replace_guided_with_retry_shadow` | `8/10 = 80.0%` | `100.0%` | `0.0%` | `5642.5` | `3351.9ms` | `2` |

Retry-shadow reason counts：

| reason | count |
| --- | ---: |
| `answer_choice_group_missing` | `1` |
| `required_terms_missing` | `1` |
| `language_requirement_failed` | `1` |

### 结论

- 新的 contract 文案已进入 system-path shadow prompt，并通过单元测试和 CLI fake gate。
- scorer 等价表达修正能覆盖已确认的词面误判，同时 fragment answer 仍然失败，不会把“可以的/嗯，对的/我查一下记忆”算成正确。
- real pregate 中 guided 达到 `80.0%`，较 replace 的 `60.0%` 提升 `20` 个百分点。
- 本次 10-case real pregate 中 retry-shadow 与 guided 持平，未观察到 P6o-24 的回退，但样本仍小，不能据此开启真实 retry。
- P6o-25 相比 P6o-24 的正式结论只能视为“小样本正向信号”：retry-shadow 从 P6o-24 的 `72.5%` 回到与 guided 持平的 `80.0%`，但样本从 `40` unique case 降到 `10` unique case，不能直接替代 P6o-24 formal。
- 下一步应执行正式 fresh workspace 40-case / 120-call 对照实验，继续保持 retry-shadow 只观测、不改变生产回复。

## P6o-26 Schema First Answer Shadow

### 修改内容

- 新增 `schema_first_shadow` prompt variant：
  - 先内部选择 `selected_facts` / current truth / ignored stale facts；
  - 再输出最终自然语言答案；
  - 仍只使用 allowed evidence，不暴露 JSON、memory id 或内部 schema 字段。
- 新增 `safe_version_replace_schema_first_shadow` eval mode：
  - 复用 safe-version replace；
  - 启用 answer candidate contract；
  - 复用 scorer-driven post-check telemetry；
  - 仍不做真实 retry、不改生产默认。
- 增加生产边界测试：
  - `schema_first_shadow` 只能来自可信 config；
  - `request.extra` 与 `session_metadata` 不能提权；
  - `MemoryConfig.safe_version_governed_mode` 默认仍为 `off`。

### 测试方法与数据

#### Focused regression

| test | result |
| --- | --- |
| contract / eval / post-check / scorer / boundary tests | `70 passed` |

Focused regression command：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_memory_system_path_safe_version_contract.py tests/test_memory_system_path_safe_version_eval.py tests/test_memory_answer_post_check.py tests/test_memory_eval_llm_sample.py tests/test_turn_pipelines.py::test_safe_version_answer_prompt_variant_flows_from_config_only tests/test_turn_pipelines.py::test_safe_version_answer_prompt_variant_extra_cannot_escalate tests/test_turn_pipelines.py::test_safe_version_answer_prompt_variant_session_metadata_cannot_escalate tests/test_default_memory_plugin_config.py -q -p no:cacheprovider
```

#### Fake-provider gate

| criterion | observed |
| --- | ---: |
| report path | `/tmp/akashic-p6o26-fake-gate-report/system_path_safe_version_eval.json` |
| case_count | `16` |
| unique_case_count | `4` |
| provider_error_count | `0` |
| timeout_count | `0` |
| `safe_version_replace_schema_first_shadow.answer_candidate_contract_enabled_rate` | `100.0%` |
| `safe_version_replace_schema_first_shadow.would_retry_count` | `4` |
| `safe_version_replace_schema_first_shadow.retry_reason_counts` | `required_terms_missing = 4`, `answer_choice_group_missing = 4` |

Privacy scan on fake output:

- no raw prompt / raw answer / session text keys in JSON;
- no fixed fake answers leaked into report text;
- passed.

#### Real pregate

| criterion | observed |
| --- | ---: |
| report path | `/tmp/akashic-p6o26-real-pregate-report/system_path_safe_version_eval.json` |
| case_count | `40` |
| unique_case_count | `10` |
| provider_error_count | `0` |
| timeout_count | `0` |
| malformed_checkpoint_line_count | `0` |
| memory_grounding_pass_rate | `100.0%` |
| forbidden_violation_rate | `0.0%` |
| token_metrics_available | `true` |

| mode | answer | grounding | forbidden | avg tokens | avg latency | would retry |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `safe_version_replace` | `8/10 = 80.0%` | `100.0%` | `0.0%` | `5355.1` | `3038.0ms` | `0` |
| `safe_version_replace_guided` | `9/10 = 90.0%` | `100.0%` | `0.0%` | `5634.6` | `4695.8ms` | `0` |
| `safe_version_replace_guided_with_retry_shadow` | `10/10 = 100.0%` | `100.0%` | `0.0%` | `5736.7` | `4143.0ms` | `0` |
| `safe_version_replace_schema_first_shadow` | `5/10 = 50.0%` | `100.0%` | `0.0%` | `5681.7` | `3478.3ms` | `5` |

Schema-first retry reasons：

| reason | count |
| --- | ---: |
| `required_terms_missing` | `3` |
| `answer_choice_group_missing` | `3` |
| `language_requirement_failed` | `1` |

### 本地诊断结论

- schema-first shadow 的主要失败集中在 preference recall、style preference、tool preference 和 hard graph bridge。
- 本地 session DB 抽查显示，schema-first 倾向于短答化、澄清化或过度保守，导致它没有比 guided 更稳。
- guided retry-shadow 在这一轮小矩阵里是最强模式，说明“先结构化再自然语言”不是单独加一个 schema 名称就会提升，关键仍是约束如何落到最终答案。

### 审阅修复与补充验证

- 修复 schema-first telemetry：`safe_version_replace_schema_first_shadow` 的 sanitized report row 现在使用 `candidate_reason = safe_version_schema_first_shadow`，不再误标为 `safe_version_guided_retry_shadow`。
- 恢复生产边界覆盖：config-only prompt variant 流转同时覆盖 `structured_guided` 和 `schema_first_shadow`。
- 补充 fake-provider telemetry gate：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o26-fake-gate-telemetry-fix-workspace --out-dir /tmp/akashic-p6o26-fake-gate-telemetry-fix-report --fake-provider --case-pack standard --balanced-small --common-limit 1 --hard-limit 1 --modes safe_version_replace_schema_first_shadow
```

| criterion | observed |
| --- | ---: |
| report path | `/tmp/akashic-p6o26-fake-gate-telemetry-fix-report/system_path_safe_version_eval.json` |
| case_count | `2` |
| unique_case_count | `2` |
| provider_error_count | `0` |
| timeout_count | `0` |
| `candidate_reason_counts` | `safe_version_schema_first_shadow = 2` |
| raw case keys | none |

补充结论：审阅指出的问题是 telemetry label bug，不影响前述 real pregate 的 answer/grounding/forbidden 结论；修复后后续 schema-first 报告可被正确归因。

### 结论

- P6o-26 证明了 schema-first 两阶段方向可以接入系统路径、也能保持 grounding/forbidden/privacy 约束，但当前 wording 和执行方式没有带来 answer uplift。
- 与 guided 相比，schema-first 明显退化到 `50%`，不应推进为默认路径。
- 与此前 P6o-25 相比，这一轮最强信号仍是 guided retry-shadow，但它仍应保持 shadow，不可直接生产激活。
- 下一步如果继续做两阶段回答，应该把重点放在“结构化选择结果如何强约束 final answer”，而不是单纯增加一个 schema-first 前缀。

## P6o-27 Best Shadow Medium Real LLM Validation

### 测试方法

| item | value |
| --- | --- |
| objective | 验证 P6o-26 小样本中表现最佳的 `safe_version_replace_guided_with_retry_shadow` 是否能在中等规模真实 LLM 测试集上超过 guided 对照 |
| case pack | `standard` |
| slice | common `20` + hard `20` = `40` unique cases |
| modes | `safe_version_replace`, `safe_version_replace_guided`, `safe_version_replace_guided_with_retry_shadow` |
| repeats | `1` |
| intended rows | `40 * 3 = 120` |
| provider | real LLM |
| timeout | `30s` |
| infra guard | `--early-infra-abort-count 3 --early-infra-abort-rate 0.5` |
| primary report | `my_md/memory_optimization/eval_reports/p6o27_best_shadow_medium_real_v1/real_balanced_40/` |
| checkpoint rebuild | `my_md/memory_optimization/eval_reports/p6o27_best_shadow_medium_real_v1/checkpoint_rebuild/` |

本轮使用 fresh workspace 和 checkpoint；没有执行真实 retry，没有修改生产默认、召回、写入或全局 prompt。

### Gate 数据

| criterion | observed |
| --- | ---: |
| case_count | `120` |
| unique_case_count | `40` |
| mode_count | `3` |
| repeat_count | `1` |
| checkpoint rows | `120` |
| provider_error_count | `0` |
| timeout_count | `0` |
| malformed_checkpoint_line_count | `0` |
| memory_grounding_pass_rate | `100.0%` |
| forbidden_violation_rate | `0.0%` |
| token_metrics_available | `true` |
| primary/rebuild mode metrics | identical |
| report privacy flags | raw query/prompt/response/session/memory summary all `false` |

### 结果数据

| mode | answer | grounding | forbidden | avg tokens | avg latency | would retry |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `safe_version_replace` | `26/40 = 65.0%` | `100.0%` | `0.0%` | `5470.85` | `3671.025ms` | `0` |
| `safe_version_replace_guided` | `31/40 = 77.5%` | `100.0%` | `0.0%` | `5514.45` | `3204.425ms` | `0` |
| `safe_version_replace_guided_with_retry_shadow` | `34/40 = 85.0%` | `100.0%` | `0.0%` | `5631.95` | `2786.55ms` | `6` |

Retry-shadow reason counts:

| reason | count |
| --- | ---: |
| `answer_choice_group_missing` | `5` |
| `required_terms_missing` | `5` |

Relative to guided, retry-shadow improved answer rate by `+7.5` percentage points and used `+117.5` average tokens, approximately `+2.13%`, without grounding or forbidden regressions.

### 结论

- 本轮中等规模真实 LLM 验证支持 retry-shadow 的正向效果：`85.0%` 高于 guided 的 `77.5%`，也高于 replace 的 `65.0%`。
- 这比 P6o-26 的 `10` unique case 小矩阵更有参考价值，且本轮 primary/rebuild、provider、timeout、privacy gate 全部通过。
- 但 P6o-24 的 40-case run 曾得到 retry-shadow `72.5%`、低于 guided `80.0%`，说明跨轮次存在明显波动。因此当前结论是“中等规模正向信号”，不是“已证明稳定最佳”。
- retry-shadow 仍然只记录 would-retry，不执行真实 retry；生产默认继续保持 `off`。
- 下一步若要决定是否进入 config-gated shadow rollout，应进行 repeat `2` 或 `3` 的稳定性验证，重点看 retry-shadow 是否在多数 repeat 中不低于 guided，以及 token 成本是否持续低于约 `5%` 增量门槛。
- retry-shadow 的 6 个失败 case 原文输入输出、错误原因和可能修复方向已记录在 [11-memory-p6o27-retry-shadow-failure-analysis.md](./11-memory-p6o27-retry-shadow-failure-analysis.md)。

## P6o-24 正式实验记录

### 测试方法

| item | value |
| --- | --- |
| objective | 完成 P6o-20 报错实验的 fresh guarded formal rerun |
| case pack | `standard` |
| slice | common `20` + hard `20` = `40` unique cases |
| modes | `safe_version_replace`, `safe_version_replace_guided`, `safe_version_replace_guided_with_retry_shadow` |
| repeats | `1` |
| intended rows | `40 * 3 = 120` |
| provider | real LLM |
| timeout | `30s` |
| infra guard | `--early-infra-abort-count 3 --early-infra-abort-rate 0.5` |
| workspace | `/tmp/akashic-p6o24-formal-real/workspace` |
| primary out-dir | `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40` |
| checkpoint | `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40/checkpoint.jsonl` |
| rebuild | `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/checkpoint_guarded_rebuild` |
| detail export | `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/answer_details` |

### Gate 数据

| criterion | observed | result |
| --- | ---: | --- |
| primary exit code | 0 | pass |
| checkpoint rebuild exit code | 0 | pass |
| case_count | 120 | pass |
| unique_case_count | 40 | pass |
| checkpoint rows | 120 | pass |
| rebuild checkpoint_input_count | 120 | pass |
| timeout_count | 0 | pass |
| provider_error_count | 0 | pass |
| empty_answer_count | 0 | pass |
| malformed_checkpoint_line_count | 0 | pass |
| primary/rebuild metrics match | true | pass |
| privacy flags | false in both JSON reports | pass |

Gate decision: `quality_passed_for_interpretation`.

### 结果数据

| mode | cases | answer | grounding | forbidden | avg tokens | avg latency | would_retry |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `safe_version_replace` | 40 | `30/40 = 75.0%` | `100.0%` | `0.0%` | `5407.575` | `3411.925ms` | 0 |
| `safe_version_replace_guided` | 40 | `32/40 = 80.0%` | `100.0%` | `0.0%` | `5485.15` | `3283.725ms` | 0 |
| `safe_version_replace_guided_with_retry_shadow` | 40 | `29/40 = 72.5%` | `100.0%` | `0.0%` | `5553.575` | `3050.95ms` | 11 |

Guided vs retry-shadow movement:

| movement | count |
| --- | ---: |
| both_passed | 25 |
| both_failed | 4 |
| guided_failed_retry_shadow_passed | 4 |
| guided_passed_retry_shadow_failed | 7 |

Retry-shadow reasons:

| reason | count |
| --- | ---: |
| `answer_choice_group_missing` | 8 |
| `required_terms_missing` | 5 |
| `language_requirement_failed` | 1 |

### P6o-24 结论

P6o-24 证明 P6o-20 的全 `answer=0` 是 infra timeout 假数据，不是方案质量失败。P6o-20 的旧 checkpoint 中 `timeout_count = 120`，空回答被评分为失败；P6o-24 fresh guarded run 中 `timeout_count = 0`、`empty_answer_count = 0`，三种模式都有正常 answer 数据。

本轮最佳是 `safe_version_replace_guided`。`safe_version_replace_guided_with_retry_shadow` 当前只适合作为诊断工具：它能发现 would-retry 原因，但修复 `4` 个 guided fail 的同时回退 `7` 个 guided pass，按预设规则判定为 `regresses`，不应推进生产默认。

## 正确率提升历程总表

| stage | 主要修改 / 测试对象 | 测试方法 | 关键数据 | 结论 |
| --- | --- | --- | --- | --- |
| Phase 6k real core eval | answer/retrieval 核心真实矩阵 | `320` unique cases，4 profiles，`1280` real rows | overall answer `23.9844%`，grounding `75.0%`，forbidden `15.7812%` | 早期真实矩阵显示回答质量低，且 grounding/forbidden 还有明显问题。 |
| Phase 6m route-governance small online | 场景路由、候选边界、三路/图谱/重排对比 | common `20` + hard `20`，4 profiles，`160` real calls | memory base `13/40 = 32.5%`；tri `17/40 = 42.5%`；graph `13/40 = 32.5%`；rerank/injection `18/40 = 45.0%`；grounding `100.0%` | 扩召回不是全局默认答案。三路和重排值得继续，图谱不能全局打开；瓶颈开始指向候选噪声和 answer layer。 |
| Phase 6m tri failure attribution | 三路召回失败归因 | report-only，不重新调用 LLM，分析 route-governance `40` 个 tri rows | tri answer fail `23/40`；grounding fail `0`；非 forbidden grounded miss `18`；forbidden failure `5` | 三路失败不是 recall miss，而是 evidence use、candidate noise、forbidden governance 和 answer constraints。 |
| Phase 6n tri answer contract | eval-only Answer Contract | common `20` + hard `20`，4 profiles，`160` real calls | memory base `35.0%`；tri `40.0%`；candidate governance `52.5%`；answer contract `75.0%`；grounding `100.0%` | 明确 must-use / allowed / forbidden / required terms 后，answer 大幅提升；answer control 是主方向。 |
| P6o-1 to P6o-4 | governed answer contract、risk-tiered candidate governance、production-safe evidence contract、post-check shadow | fake/offline wiring + shadow checks | P6o-1 fake `200` rows；P6o-2 offline `80` cases，protected expected hit loss `0`；P6o-4 only shadow no retry | 把 oracle answer contract 往 production-safe contract 迁移，仍不改生产默认。 |
| P6o-5 small real A/B | candidate governance + production-safe evidence contract | common `20` + hard `20`，4 profiles，`160` real calls | tri `37.5%`；candidate governance `50.0%`；answer contract `80.0%`；governed answer contract `39/40 = 97.5%`，grounding `100.0%`，forbidden `0.0%` | 候选治理 + production-safe evidence contract 在 eval harness 上同时提高 answer 并清零 forbidden。 |
| P6o-6 to P6o-10 | rerank signal、version boundary、安全表达、组合验证 | 多个 common `20` + hard `20` 小矩阵 | P6o-6 rerank-governed `40/40 = 100.0%`；P6o-8 safe presentation version-governed `39/40 = 97.5%`；P6o-10 version-governed `40/40 = 100.0%`，combo `39/40 = 97.5%` | eval harness 的最佳单项是 safe version-governed；rerank/组合安全，但没有稳定超过 version-only。 |
| P6o-12 repeat stability | safe version-governed repeat stability | `40` cases，2 profiles，3 repeats，`240` real calls | governed `119/120 = 99.1667%`；version-governed `117/120 = 97.5%`；grounding `100.0%`，forbidden `0.0%` | eval-only 最强方案在当前 40-case slice 稳定在 `39/40` 到 `40/40` 区间，但仍不是 production system-path。 |
| P6o-13 system-path migration | 把 safe-version governed 迁入真实 system path 可测试链路 | fake-provider system-path smoke，40 unique，3 modes，`120` rows | contract generation `100.0%`，post-check shadow `100.0%` for safe modes | 真实 `AgentLoop -> retrieval -> memory block -> prompt` 链路可挂载 contract；生产默认仍 `off`。 |
| P6o-14 system-path real A/B | `current` vs `safe_version_replace` | common `20` + hard `20`，2 modes，`80` real calls | current `11/40 = 27.5%`，forbidden `32.5%`；replace `21/40 = 52.5%`，forbidden `0.0%`，grounding `100.0%` | system-path 中 safe version replacement 明显优于 current，但没有复现 eval-only 97.5%。 |
| P6o-15 repeat stability | system-path `current` vs `safe_version_replace` 稳定性 | common `20` + hard `20`，2 modes，3 repeats，`240` real calls | current `31/120 = 25.8333%`，forbidden `39.1667%`；replace `88/120 = 73.3333%`，forbidden `0.0%`，grounding `100.0%`；replace repeat `72.5/72.5/75.0%` | P6o-14 的 `52.5%` 不是稳定上限；system-path replace 稳定在约 `73%`，瓶颈转向 evidence-to-answer。 |
| P6o-16 answer guidance | 在 safe version replacement contract 中加入 production-safe answer guidance | common `20` + hard `20`，3 modes，`120` real calls | current `25.0%`；replace `65.0%`；guided `72.5%`；guided vs replace `+7.5` points，forbidden `0.0%` | 通用 answer guidance 有同场提升，不破坏 grounding/forbidden/token gate。 |
| P6o-17 guided repeat | guided vs replace repeat confirmation | common `20` + hard `20`，2 modes，3 repeats，`240` real calls | replace `77/120 = 64.1667%`；guided `80/120 = 66.6667%`；guided delta `+2.5` points；guided not-lower `2/3` | guided 是小幅、repeat-confirmed 的正增益层，但不能直接生产默认开启。 |
| P6o-18 prompt variants | structured guided / near-query block A/B 和失败归因 | common `20` + hard `20`，4 modes，`160` real calls | replace `60.0%`；guided `77.5%`；structured `77.5%`；near-query `57.5%`；guided miss `9/40` = required-term `5`、any-group `2`、language `2` | structured 只交换 wins/losses，near-query 明显回退；剩余问题集中在 answer expression，不是 recall/safety/infra。 |
| P6o-19/P6o-20 retry-shadow attempt | Answer Candidate Contract + Post-check Retry Shadow；per-case detail export | P6o-19 fake smoke；P6o-20 real `120` target rows | P6o-20 timeout `120/120`，answer 全 `0`，movement `both_failed=40` | P6o-20 是 infra-blocked，不可解释质量；需要 fresh checkpoint 和 early infra abort guard。 |
| P6o-21/P6o-22 infra diagnosis and guard | timeout/provider failure 诊断；early infra abort guard | old checkpoint forensic + fake abort + fresh real mini | old P6o-20 guarded rebuild exit `2`，`quality_interpretation_allowed=false`；fresh mini `9` rows timeout `0`，answer data non-empty | 修复评测可信度：infra-heavy run 不再伪装成质量报告。 |
| P6o-23 formal pregate | 正式实验前 real path gate | `10` unique cases，3 modes，`30` real rows | timeout `0`，provider error `0`，empty answer `0`，answer `60.0%`，grounding `100.0%` | 真实评测链路健康，可以执行 P6o-24 formal run。 |
| P6o-24 formal guarded real | 完成 P6o-20 报错实验的 fresh formal run | `40` unique cases，3 modes，`120` real rows，fresh checkpoint + guarded rebuild | replace `75.0%`；guided `80.0%`；retry-shadow `72.5%`；timeout/provider/empty/malformed 均 `0` | 当前最佳 system-path 是 guided；retry-shadow 当前回退，只保留诊断价值。 |

## 关键修改线索

| direction | 做过的修改 | 数据变化 | 当前判断 |
| --- | --- | --- | --- |
| 扩大召回 / 三路 / 图谱 | tri retrieval、graph retrieval、rerank injection、route governance | route-governance 小矩阵中 tri `32.5% -> 42.5%`，rerank `32.5% -> 45.0%`，graph 同场未超过 base | 单纯扩大召回不够，graph 不应 all-on；要路由和治理。 |
| 候选治理 | strict candidate governance、risk-tiered governance、forbidden/superseded/scope 过滤 | tri candidate governance 从 P6n 的 `40.0%` tri 提到 `52.5%`，forbidden 可降到 `0.0%` | 输入侧去噪有效，但不足以单独解决 answer。 |
| Answer Contract | must-use / allowed / forbidden / required terms / required groups | P6n answer contract `75.0%`，P6o5 governed contract `97.5%` | 这是从 recall 问题转向 answer control 后的最大增益来源。 |
| Production-safe evidence contract | 去掉 fixture answer expectations，使用 tiered candidate metadata、safe evidence、version boundary | P6o5 governed `97.5%`，P6o10 version-governed `100.0%`，P6o12 repeat `97.5%` | eval harness 中表现强，但需要 system-path 迁移验证。 |
| Safe version replacement system-path | 将 contract 挂到真实 AgentLoop/retrieval/memory block/prompt path | P6o14 current `27.5%` -> replace `52.5%`；P6o15 repeat replace `73.3333%` | 生产形态有效，且清零 forbidden，但 system-path 难度高于 eval harness。 |
| Answer guidance | 在 safe version replacement 上加入通用 answer guidance | P6o16 replace `65.0%` -> guided `72.5%`；P6o17 repeat `64.1667%` -> `66.6667%`；P6o24 `75.0%` -> `80.0%` | 有小幅到中等正增益，是当前 system-path 最好方向。 |
| Prompt variant / placement | structured guided、near-query block | P6o18 structured `77.5%` 与 guided 打平但更贵；near-query `57.5%` 明显回退 | 当前 wording 不应继续推进。 |
| Post-check retry shadow | Answer Candidate Contract + post-check would-retry reason | P6o24 retry-shadow `72.5%`，低于 guided `80.0%`；修复 `4`、回退 `7` | 作为诊断有价值，当前不能生产化或真实 retry。 |
| Eval infra guard | checkpoint resume/report-only 修复、early infra abort、fresh gate | P6o20 全 timeout answer `0` 被判定 invalid；P6o24 fresh run timeout/empty `0` | 解决的是评测可信度，不是直接提升 answer，但避免错误结论。 |

## 下一步建议

| priority | next experiment | reason | success criteria |
| --- | --- | --- | --- |
| P0 | 针对 P6o-24 的 `7` 个 guided pass -> retry-shadow fail 回退做 answer-selection 修订 | 当前 retry-shadow 回退大于修复，必须先减少 contract-induced omissions | retry-shadow 不低于 guided；grounding `100.0%`；forbidden `0.0%`；无 token blow-up |
| P1 | 针对 guided miss set 做小改动 A/B | P6o-18/P6o-24 都显示剩余 miss 是 required-term、any-group、language failure | guided answer 超过 `80.0%`，且不回退 current guided pass |
| P1 | 保持 P6o-22/P6o-24 gate 作为正式实验默认 | 避免 timeout/provider failure 再次污染质量结论 | timeout/provider/empty/malformed 均为 `0`，primary/rebuild metrics 一致 |
| P2 | 设计 config-gated shadow rollout 文档 | P6o-17 已证明 guided 是小幅 repeat-confirmed positive layer | 只记录 telemetry，不改变 production reply/default |
