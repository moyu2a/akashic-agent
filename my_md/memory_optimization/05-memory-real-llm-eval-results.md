# Memory Real LLM Eval Results

## 目标

记录 phase6k 的真实 LLM 量化结果，区分已经拿到的在线证据和仍然只有离线/投影证据的部分。

## 评测范围

- 真实 provider。
- 核心回答 / 召回矩阵。
- 通过 checkpoint JSONL 保证中断后可续跑。
- 配套目标指标投影报告。

## 基线与控制组协议

本报告统一采用以下 profile 语义：

```text
off / chain_off = 关闭增强控制组
memory_base / chain_memory_base = 原始记忆基线
增强模块 = 在原始记忆基线上叠加写入价值、三路召回、图谱召回、重排、版本链与溯源、睡眠巩固
```

`off` 只用于说明“完全关闭增强”时会发生什么；`memory_base` 才用于衡量“原本记忆 + 新增增强”的效果。带版本链的评测使用 `chain_off` 与 `chain_memory_base`，两者分别对应关闭增强控制组和原始记忆基线。

召回主表统一按 case 的目标记忆命中情况统计：

```text
成功召回数 = 命中的目标记忆条数
未召回数 = 总 case 数 - 成功召回数
召回率 = 成功召回数 / 总 case 数
多召回条数 = 当前 profile 成功召回数 - 基准成功召回数
召回率提升百分点 = 当前召回率 - 基准召回率
```

表中的“基准”默认是同一链路下的 `memory_base` 或 `chain_memory_base`，而不是 `off` 或 `chain_off`。

## 指标解释

这三个指标都是按 case 统计的回答层指标，不是记忆库健康分，也不是生产准确率。

- `answer_rule_pass_rate`：回答是否满足预设规则。规则包括必须出现的词/短语、必须命中的“任一即可”词组、禁止词检查，以及语言要求；它只看回答文本本身。
- `memory_grounding_pass_rate`：回答是否真正用到了期望的记忆 id。只要 `expected_memory_ids` 都出现在 `used_memory_ids` 里，就算通过。
- `forbidden_violation_rate`：回答里出现了多少 case 的禁止项。只要命中一个 forbidden term，该 case 就算违规。

简单说：

- `answer_rule_pass_rate` = 回答规则通过率
- `memory_grounding_pass_rate` = 记忆证据命中率
- `forbidden_violation_rate` = 禁用内容违规率

## 最终结果

样本规模口径：

```text
unique_case_count = 320
common_case_count = 160
hard_case_count = 160
case_count = 1280 表示在线记录行数，不表示唯一 case 数
```

| 项目 | 结果 |
| --- | --- |
| `case_count` | `1280` |
| `unique_case_count` | `320` |
| `profile_count` | `4` |
| `repeat_count` | `1` |
| `answer_rule_pass_rate` | `23.9844%` |
| `memory_grounding_pass_rate` | `75.0%` |
| `forbidden_violation_rate` | `15.7812%` |
| `avg_latency_ms` | `4639.9172` |
| `total_token_count` | `6971048` |
| `infra_passed` | `true` |
| `answer_quality_passed` | `false` |

## 目标指标投影

配套目标指标报告的关键状态是：

- `measurement_mode=offline_trace_real_baseline_plus_online_checkpoint_target_metrics`
- `case_count=320`
- `online_row_count=4`
- `online_answer_record_count=1280`
- `online_write_record_count=0`
- `online_hygiene_record_count=0`

这说明当前在线证据只覆盖到了三路召回的在线 checkpoint 行，写入治理和记忆卫生没有真实 LLM 记录。

## 三张主表

### 1. 召回与回答增益表

| 当前 profile | 证据层级 | 成功召回数 | 未召回数 | 召回率 | 多召回条数 | 召回率提升百分点 | 说明 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `memory_base` | online_checkpoint | unavailable | unavailable | unavailable | unavailable | unavailable | 原始记忆基线；当前报告未提供按目标记忆条数拆分的结果 |
| 三路召回增强 | online_checkpoint | unavailable | unavailable | unavailable | unavailable | unavailable | 相对 `memory_base` 的模块级增益还需要独立 ablation |
| 图谱召回增强 | gated | unavailable | unavailable | unavailable | unavailable | unavailable | 没有真实 online row，仍是离线/投影证据 |
| 重排与注入治理增强 | gated | unavailable | unavailable | unavailable | unavailable | unavailable | 没有真实 online row，仍是离线/投影证据 |
| 版本链与溯源增强 | gated | unavailable | unavailable | unavailable | unavailable | unavailable | 没有真实 online row，仍是离线/投影证据 |

### 2. 写入治理增益表

| 模块 | 证据层级 | candidate 数 | before | after | 提升百分点 | 相对提升 | 说明 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 写入价值治理 | offline_proxy | 0 | unavailable | unavailable | unavailable | unavailable | 本次 `online_write_record_count=0`，没有真实 LLM 写入证据 |

### 3. 记忆库卫生增益表

| 模块 | 证据层级 | scanned 数 | before | after | 提升百分点 | 相对提升 | 说明 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 睡眠巩固 | offline_proxy | 0 | unavailable | unavailable | unavailable | unavailable | 本次 `online_hygiene_record_count=0`，没有真实 LLM 卫生证据 |

## 结论

1. 真实 LLM 评测链路已经打通。
2. 回答与召回主矩阵有了可引用的量化结果。
3. 写入治理、睡眠巩固、记忆库卫生还不能写成真实线上提升结论。
4. 后续如果要继续量化 `phase2-5`，需要给每个开关单独补真实 LLM 证据，而不是只复用本次核心矩阵。

## 原始报告

- `/tmp/akashic-memory-phase6k-real/reports/memory_comprehensive_online_eval.json`
- `/tmp/akashic-memory-phase6k-real/reports/memory_comprehensive_online_eval.md`
- `/tmp/akashic-memory-phase6k-real/reports/memory_comprehensive_online_eval.checkpoint.jsonl`
- `/tmp/akashic-memory-phase6k-target/memory_target_metrics_eval.json`
- `/tmp/akashic-memory-phase6k-target/memory_target_metrics_eval.md`
