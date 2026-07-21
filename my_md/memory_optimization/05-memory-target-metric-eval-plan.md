# Memory Target Metric Eval Plan

## 目标

这份文档记录 Phase 6 后续评测口径调整：从“一个综合分解释所有模块”改成“三组目标指标百分比评测”。

核心目标不是证明某个总分更高，而是回答更具体的问题：

```text
打开某个 memory 模块后，它负责的那类问题具体改善了多少？
```

例如：

- 三路召回是否让目标记忆召回率提高。
- 图谱召回是否让模糊实体关联命中率提高。
- 重排和注入治理是否让错误注入率下降。
- 版本链与溯源是否让旧版本误用率下降、回源率提高。
- 写入价值治理是否让污染写入拦截率提高。
- 睡眠巩固是否让重复合并率、低价值清理率和 token 节省率提高。

## 为什么要改口径

上一轮离线三层评分已经把 `answer_layer`、`write_governance` 和 `memory_hygiene` 分开，但仍然存在一个解释问题：

```text
不是每个模块都会影响每一层分数。
```

具体表现是：

- `write_governance` 只读取 `write_value_score` trace，所以从写入价值治理开启后一直保持相同分数。
- `memory_hygiene` 只读取 `sleep_consolidation_shadow` trace，所以前面召回、图谱、重排、版本链阶段都是 unavailable。
- 三路召回、图谱召回、重排和版本链主要影响回答层，不能公平体现写入治理或长期库卫生。

如果继续用单一综合分或三层总分，很容易误判：

- 睡眠巩固本来是后台清理能力，却会因为即时回答分不高被看成“没提升”。
- 写入价值治理本来是减少污染写入，却会因为当前轮没有注入证据被看成“对回答没帮助”。
- 版本链与溯源本来是降低旧记忆误用和提升可信度，却会被平均到回答分里。

所以后续评测应改成：

```text
回答效果组：评估召回、图谱、重排、版本链对回答和证据的影响。
写入治理组：评估写入价值治理对污染、重复、误写的影响。
记忆库卫生组：评估睡眠巩固和溯源对长期记忆库健康度的影响。
```

## 这样做的好处

### 1. 模块目标和指标一一对应

三路召回不需要证明“写入治理变好”，它只需要证明目标记忆召回率、证据命中率和回答命中率变好。

写入价值治理不需要证明“当前轮回答更好”，它只需要证明污染写入拦截率、有效写入精度和重复控制率变好。

睡眠巩固不需要证明“下一句回答立刻更好”，它只需要证明重复合并、过期清理、低价值清理、回源健康度和 token 节省变好。

### 2. 百分比比综合分更容易解释

推荐表达：

```text
开启三路召回后，目标记忆召回率从 A% 提升到 B%，提升 C 个百分点，相对提升 D%。
```

不推荐表达：

```text
整体性能提升 596%。
```

因为“性能”太泛，且 baseline 很低时百分比会被放大。更稳妥的展示方式是同时给出：

- 开启前百分比。
- 开启后百分比。
- 提升百分点。
- 相对提升百分比。

### 3. 更适合真实 LLM 评测

真实 LLM 会受到提示词、上下文、模型采样、token 成本和 provider 状态影响。按目标指标拆分后，即使某个模块没有拉高最终答案，也能判断它是否完成了自己的工程职责：

- 是否成功召回。
- 是否成功注入。
- 是否成功拒写。
- 是否成功回源。
- 是否成功清理。
- 是否降低错误率或 token 成本。

## 三组测试设计

### 1. 回答效果组

覆盖模块：

- 三路召回。
- 图谱召回。
- 重排与注入治理。
- 版本链与溯源。

核心指标：

```text
目标记忆召回率 = 命中 expected_memory_ids 的 case 数 / 有 expected_memory_ids 的 case 数
证据命中率 = 命中 expected_source_refs 或可回源证据的 case 数 / 需要证据的 case 数
回答命中率 = 最终回答满足 answer expectation 的 case 数 / 总 case 数
错误召回率 = 召回 forbidden_memory_ids 的 case 数 / 有 forbidden_memory_ids 的 case 数
错误注入率 = forbidden_memory_ids 被注入 prompt 的 case 数 / 有 forbidden_memory_ids 的 case 数
旧版本误用率 = superseded / stale memory 被使用的 case 数 / 有旧版本干扰的 case 数
```

推荐展示：

```text
开启三路召回后，目标记忆召回率从 A% 提升到 B%，提升 C 个百分点。
开启图谱召回后，模糊实体关联类命中率从 A% 提升到 B%。
开启重排与注入治理后，错误注入率从 A% 下降到 B%。
开启版本链与溯源后，旧版本误用率从 A% 下降到 B%，回源成功率从 C% 提升到 D%。
```

### 2. 写入治理组

覆盖模块：

- 写入价值治理。

核心指标：

```text
有效写入精度 = 正确允许写入的候选数 / 实际允许写入候选数
污染写入拦截率 = 正确拒绝的污染候选数 / 所有污染候选数
重复控制率 = 被拒绝或强化的重复候选数 / 所有重复候选数
冲突转审率 = 标记为 review 的冲突候选数 / 所有冲突候选数
写入减少率 = 1 - 新方案写入数 / baseline 写入数
误拒率 = 错误拒绝的有效记忆数 / 所有有效记忆数
误收率 = 错误允许的污染记忆数 / 所有污染候选数
```

推荐展示：

```text
开启写入价值治理后，污染写入拦截率从 A% 提升到 B%。
重复写入控制率从 A% 提升到 B%。
有效写入精度从 A% 提升到 B%。
```

### 3. 记忆库卫生组

覆盖模块：

- 睡眠巩固。
- 层级溯源。
- 版本链的库级一致性信号。

核心指标：

```text
重复合并率 = 正确识别并合并的重复组 / 标注重复组
过期清理率 = 正确标记 stale 的旧状态记忆 / 标注旧状态记忆
低价值清理率 = 正确降权或清理的低价值记忆 / 标注低价值记忆
source_ref 覆盖率 = 带可用 source_ref 的记忆 / 总记忆
回源成功率 = fetch_messages 成功找到证据的记忆 / 带 source_ref 的记忆
token 节省率 = 预计减少 token / 原始注入 token
巩固后召回保持率 = 巩固后仍能召回目标记忆的 case / 巩固前可召回 case
```

推荐展示：

```text
开启睡眠巩固后，重复记忆合并率达到 A%。
预计 prompt token 节省 B%。
source_ref 回源成功率从 C% 提升到 D%。
巩固后目标记忆召回保持率为 E%。
```

## 测试集规模

当前实现采用双档 case pack：

| case pack | case 数 | 目的 |
| --- | ---: | --- |
| `standard` | 80 | 默认标准集，common 40 / hard 40，用来复现 Phase 6d-6i 的既有报告。 |
| `comprehensive` | 320 | 完整目标导向集，common 160 / hard 160，用来扩大覆盖面并准备后续真实 LLM 大样本测试。 |

完整集覆盖 20 类场景、8 个变体，包括普通偏好、事实、项目记忆、模糊指代、相似实体、跨 session、冲突纠错、旧版本干扰、临时信息、助手推断、重复写入、低价值信息、污染写入、实体别名、信息熵写入价值和睡眠压缩后召回保持。

运行完整集离线目标指标：

```bash
.venv/bin/python scripts/run_memory_target_metrics_eval.py \
  --out-dir /tmp/akashic-memory-comprehensive-pack \
  --case-pack comprehensive
```

本轮 smoke 已跑通完整集，生成 320 case、960 个写入候选、2400 个记忆库卫生扫描单元。它证明完整集能被现有 runner 消费，但结果仍是离线 shadow/proxy，不是线上真实 LLM 结论。

真实 LLM core matrix 也已经开始写 checkpoint：

```text
320 cases * 4 profiles * 1 prompt variant * 1 repeat = 1280 runs
```

本轮在 325 条真实调用后手动停止，并重建 checkpoint 报告：

```text
/tmp/akashic-memory-phase6k-real/checkpoint-report/memory_comprehensive_online_eval.json
/tmp/akashic-memory-phase6k-real/checkpoint-report/memory_comprehensive_online_eval.md
```

该 checkpoint 报告只覆盖 answer/retrieval 的部分真实 rows，不应被当成完整 1280-run 的最终结论。后续若继续跑，应通过 `--resume` 复用同一 checkpoint 路径。

## 真实 LLM 接入方式

真实 LLM 评测不应写生产 memory DB。推荐流程：

```text
构造临时 workspace
  -> 构造受控 memory engine / cloned memory snapshot
  -> 真实 AgentLoop.process_direct()
  -> 真实 LLM 生成最终回答
  -> 记录召回、注入、写入、回答、token、延迟
  -> judge 根据标注规则计算目标百分比
```

真实 LLM runner 必须保留：

- `--enable-real-llm` 显式开关。
- checkpoint jsonl。
- `--resume` 续跑。
- provider error / timeout 单独记录。
- 报告中区分基础设施失败和答案质量失败。
- 常规报告脱敏；完整回答和证据块只能在临时 workspace 的 debug 目录输出。

当前已有 `scripts/run_memory_comprehensive_online_eval.py`，后续目标指标报表应复用它的真实 LLM checkpoint，而不是重复消耗一遍 provider 调用。

## 写入治理和记忆库卫生 evidence 输入

写入治理和记忆库卫生不能从 answer checkpoint 里推断。answer checkpoint 只能说明最终回答、引用和违规情况，不能证明某个候选记忆是否应该写入，也不能证明长期记忆库是否真的被清理。

因此，这两组指标需要单独的 evidence 文件。当前 `scripts/run_memory_target_metrics_eval.py` 支持三种输入格式：

```text
JSON 数组
{"records": [...]} 包裹 JSON
JSONL
```

写入治理 evidence 每行必须包含：

```text
candidate_id
baseline_decision   # allow | reject | review
after_decision      # allow | reject | review
label               # useful | pollution | duplicate | conflict
infra_error         # true | false，必须是真布尔值
```

记忆库卫生 evidence 每行必须包含：

```text
item_id
baseline_state          # active | merged | stale | low_value_removed
after_state             # active | merged | stale | low_value_removed
label                   # duplicate | stale | low_value | retained
source_ref_available    # true | false，必须是真布尔值
source_fetch_success    # true | false，必须是真布尔值
baseline_token_estimate # 非负数字，不能是字符串或布尔值
after_token_estimate    # 非负数字，不能是字符串或布尔值
infra_error             # true | false，必须是真布尔值
```

示例命令：

```bash
.venv/bin/python scripts/run_memory_target_metrics_eval.py \
  --out-dir my_md/memory_optimization/eval_reports \
  --online-checkpoint-source real_llm \
  --online-write-evidence-json /path/to/write_evidence.jsonl \
  --online-hygiene-evidence-json /path/to/hygiene_evidence.jsonl
```

如果 evidence 文件缺字段、label / decision / state 不在允许范围内、布尔字段用字符串表示、token 估算不是非负数字，脚本会直接失败，不会把坏数据写进报表。

## 三张主表

### 召回与回答增益表

| 模块 | case 数 | 目标召回率 before | 目标召回率 after | 提升百分点 | 相对提升 | 回答命中率 after | 证据命中率 after | 错误召回率 after | 错误注入率 after |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |

### 写入治理增益表

| 模块 | candidate 数 | 有效写入精度 before | 有效写入精度 after | 污染拦截率 before | 污染拦截率 after | 重复控制率 after | 写入减少率 after | 误拒率 after |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |

### 记忆库卫生增益表

| 模块 | scanned 数 | 重复合并率 after | 过期清理率 after | 低价值清理率 after | source_ref 覆盖率 after | 回源成功率 after | token 节省率 after | 巩固后召回保持率 after |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |

## 当前执行结果：Phase 6h 分母与冲突链修订版

当前已经完成第二次修订：先把第一版 `before = 0` 的展示口径改成真实 baseline 口径，再修复真实 baseline 下暴露的两个问题：

- 版本链不再用通用 `should_recall_ids` 计算 active leaf 命中，而是新增 `expected_active_version_ids` 和 `expected_stale_version_ids`。
- Phase 6h 增加一个 forked replacement-chain fixture，使 `conflict_chain_detection_rate` 变成可测指标。
- Phase 6h 把图谱召回分母从通用 `should_recall_ids` 改为 `expected_graph_recall_ids`，避免图谱模块被 tri-retrieval-only 的 `_target` miss 惩罚。
- hard case 中新增显式 `baseline_miss_recall_ids`，让 baseline 在部分目标导向难例中故意 miss，而三路召回 / 图谱召回 / 重排注入 / 版本链实验路径仍可恢复目标。
- Markdown 报告新增“版本链专项指标”，避免新语义只存在 JSON 中。

正式离线报告路径：

```text
my_md/memory_optimization/eval_reports/memory_target_metrics_eval.json
my_md/memory_optimization/eval_reports/memory_target_metrics_eval.md
```

当前正式报告：

```text
measurement_mode = offline_trace_real_baseline_target_metrics
online_status = gated_no_checkpoint
online_row_count = 0
```

这仍然是离线 trace / proxy 指标，不是真实线上 LLM 结果，也不代表生产准确率。

### Phase 6h 主要结论

召回与回答组：

| 模块 | 目标召回率 before | 目标召回率 after | 结论 |
| --- | ---: | ---: | --- |
| 三路召回 | 93.75% | 100% | 增加 hard miss 后，三路召回能恢复被 baseline 漏掉的目标，提升 6.25 个百分点。 |
| 图谱召回 | 97.5% | 100% | 图谱召回按 graph 专用目标分母计算，提升 2.5 个百分点；上一轮 `98.75%` 缺口是分母混入 tri target。 |
| 重排与注入治理 | 93.75% | 100% | 在当前离线链路中，重排/注入治理保持目标召回并把错误注入控制到 0%。 |
| 版本链与溯源 | 90% | 100% | active 当前版本召回率从 90% 到 100%，不再出现旧口径的 `100% -> 50%` 假下降。 |

hard 子集：

| 模块 | hard before | hard after | 结论 |
| --- | ---: | ---: | --- |
| 三路召回 | 87.5% | 100% | hard miss 主要体现在难例集，三路召回提升 12.5 个百分点。 |
| 图谱召回 | 95% | 100% | 图谱召回提升 5 个百分点；graph 专用目标全部恢复。 |
| 重排与注入治理 | 87.5% | 100% | hard 难例中目标召回恢复到 100%，错误注入 after 为 0%。 |
| 版本链与溯源 | 80% | 100% | 当前有效版本召回率提升 20 个百分点。 |

版本链专项指标：

| case_set | current_version_recall_rate before | current_version_recall_rate after | stale_version_misuse_rate before | stale_version_misuse_rate after | conflict_chain_detection_rate |
| --- | ---: | ---: | ---: | ---: | --- |
| common | 100% | 100% | 0% | 0% | unavailable |
| hard | 80% | 100% | 0% | 0% | 100% |
| overall | 90% | 100% | 0% | 0% | 100% |

写入治理组：

```text
candidate_count = 240
有效写入精度 before = 0%
有效写入精度 after = unavailable
污染拦截率 after = 100%
重复控制率 after = 80%
写入减少率 after = 100%
误拒率 after = 0%
```

其中 `污染拦截率 before`、`重复控制率 before` 等没有真实 baseline 决策计数的字段现在显示 `unavailable`，不再假写 0。

记忆库卫生组：

```text
scanned_count = 600
重复合并率 after = 10%
过期清理率 after = 13.3929%
低价值清理率 after = 13.3929%
source_ref 覆盖率 after = 86.6072%
回源成功率 after = 100%
token 节省率 after = 33.482%
巩固后召回保持率 after = 100%
```

其中重复合并、过期清理、低价值清理的 before 如果没有 baseline cleanup 事件，显示 `unavailable`；`token_saving_rate_before = 0` 是因为 baseline 明确定义为“不压缩、不节省 token”。

### 这轮结果说明什么

Phase 6h 比上一轮更可信，因为它解决了两个展示误导：

- 不再用 `0% -> 100%` 夸大模块增益。
- 不再把版本链 active leaf 和非版本图谱记忆混在同一个分母里。
- 不再把图谱召回和三路召回的目标分母混在一起。
- hard miss 明确写在 case expectation 中，因此 normal case 的 validation 没有被全局放宽。

但它仍有局限：

- hard miss 是目标导向离线构造，不是线上真实用户自然分布。
- 写入治理和睡眠巩固仍是 shadow / dry-run 指标，不代表真实 DB 已写少、已清理或真实 prompt token 已下降。
- 冲突链识别当前仅由一个 forked replacement chain 支撑，还需要更多分叉类型和回滚场景。

### 治理类指标和版本链审阅结论

| 模块 | 当前判断 | 问题 | 后续修订方向 |
| --- | --- | --- | --- |
| 重排与注入治理 | 相对合理 | 目标召回率没有提升，但错误召回率和错误注入率 after 都是 `0%`，说明它主要体现过滤和注入治理价值。 | 继续保留该指标，但后续补更多 forbidden / 相似干扰 case。 |
| 写入价值治理 | 方向合理但不完整 | 污染拦截率 after `100%`、写入减少率 after `100%` 容易被“全拒绝”放大；有效写入精度 after 是 `unavailable`，说明当前没有允许写入的有效分母。 | 补有效候选保留率、有用记忆未来召回率、真实误拒率和误收率。 |
| 睡眠巩固 | 方向合理但仍是 shadow | token 节省率 after `33.482%`、召回保持率 after `100%` 是 dry-run 估算，不代表真实 DB 已清理或真实 prompt token 已下降。 | 补真实执行或线上 evidence：巩固前后 active 数、真实 prompt token、关键记忆保护率、巩固后真实召回准确率。 |
| 版本链与溯源 | 口径已修订且冲突链可测 | 当前有效版本召回率已经可解释，冲突链识别率 after 为 `100%`。 | 后续补更多冲突链类型和线上 evidence。 |

### 下一步计划

优先级仍然不是马上继续真实 LLM 长跑，而是先补齐离线指标剩余盲点：

1. 补写入治理的“有效候选保留率”和“误拒率”fixture，避免只看到全拒绝带来的高拦截率。
2. 补睡眠巩固的真实 token / active 数 evidence 输入，区分 dry-run 估算和真实效果。
3. 扩展冲突链 fixture 类型，例如多层分叉、回滚分叉和跨 source_ref 分叉。
4. 再把已有 Phase 6e checkpoint 转成新版目标指标表；如果 checkpoint 仍不完整，再考虑恢复 provider 后续跑。

随后在真实 LLM 层复用 Phase 6e 的 checkpoint：

- 如果已有完整 checkpoint，就从 checkpoint 重建回答层目标指标报表。
- 如果 provider 余额恢复，用 `--resume` 补齐真实调用，再生成完整真实 LLM 目标指标报表。
- 写入治理和记忆库卫生的线上层需要额外 evidence 事件或 JSON 输入；没有这些事件时必须显示 unavailable。

这样能保证：

- 先有稳定、可测试、可复现的报表结构。
- 再把真实 LLM 的不稳定性和成本放到 runner 层处理。
- 不把“provider 余额不足”误判成 memory 模块效果不好。
