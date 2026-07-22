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

补充：睡眠巩固 evidence 评测已经把这个口径落到可运行脚本。`scripts/run_memory_sleep_hygiene_evidence_eval.py` 默认构造 600 个目标导向 case，扫描 750 条 active item，并输出 `online_hygiene_records` 兼容 evidence。当前结果用于第三张主表“记忆库卫生表”，不用于回答层召回增益表。

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

当前睡眠巩固 evidence 评测结果：

| 指标 | 数值 |
| --- | ---: |
| case 数 | 600 |
| 扫描 active item 数 | 750 |
| evidence row 数 | 600 |
| 重复候选识别率 | 100.0% |
| 过期候选识别率 | 100.0% |
| 低价值候选识别率 | 100.0% |
| 来源覆盖率 | 90.0% |
| proxy 回源成功率 | 100.0% |
| shadow 估算 token 节省率 | 64.0138% |
| 关键记忆保持率 | 100.0% |
| 关键记忆误伤候选数 | 0 |
| 非预期候选数 | 0 |
| 误伤候选率 | 0.0% |
| 实际应用变更数 | 0 |

这些数值来自离线 evidence / shadow-only 评测。`source_fetch_success_rate` 当前只表示有 `source_ref` 的行在 proxy 口径下可回源，不代表已经真实读取历史消息；`shadow_estimated_token_saving_rate` 也只是候选层估算，不代表真实 DB 或真实 prompt token 已下降。

睡眠巩固 V2 不只看候选识别率，还看 `candidate precision` 和 `retained protection`。这样能避免“只要把所有东西都标成可清理，recall 就很好看”的问题。当前 `memory_target_metric_sleep_hygiene.md` 仍只输出一行 `online_evidence` 记忆库卫生指标；standard / hard / overall 的细分结果在 dedicated sleep hygiene report 中展示。

V2 hard / adversarial 报告结果：

| case_set | case 数 | evaluated item 数 | candidate recall | candidate precision | retained protection | false positive cleanup | safe evidence token saving |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| standard | 600 | 600 | 100.0% | 100.0% | 100.0% | 0.0% | 64.0138% |
| hard | 320 | 520 | 100.0% | 75.0% | 90.0% | 10.0% | unsafe |
| overall | 920 | 1120 | 100.0% | 93.4426% | 92.7273% | 7.2727% | unsafe |

这说明 standard 集可以证明基础链路稳定，hard 集可以暴露边界误伤。当前 hard 集里主要问题是相似但不应清理的 near-merge 场景会进入候选，从而把安全 token saving 标记为 `unsafe`。

V3 安全候选口径已经把这个问题拆开：`cleanup candidate` 表示可以进入严格 dry-run patch 的清理动作，`merge suggestion` 表示有相似信号但只能复核，不能直接清理。当前 V3 正式报告路径是 `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence_v3/`。

| case_set | case 数 | evaluated item 数 | cleanup recall | cleanup precision | retained protection | false positive cleanup | merge suggestion | review required | safe cleanup token saving |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| standard | 600 | 600 | 100.0% | 100.0% | 100.0% | 0.0% | 0 | 0 | 64.0138% |
| hard | 320 | 520 | 100.0% | 100.0% | 100.0% | 0.0% | 40 | 120 | 23.7952% |
| overall | 920 | 1120 | 100.0% | 100.0% | 100.0% | 0.0% | 40 | 120 | 42.5121% |

这张表的解释口径：

| 字段 | 含义 |
| --- | --- |
| `cleanup recall` | 应该被清理的记忆里，有多少被识别为安全清理候选。 |
| `cleanup precision` | 被识别为安全清理候选的记忆里，有多少确实应该清理。 |
| `retained protection` | 应该保留的关键记忆里，有多少没有被误伤。 |
| `false positive cleanup` | 应该保留的记忆被错误当成清理候选的比例。 |
| `merge suggestion` | 相似但不确定的合并建议数量，只进入复核，不直接清理。 |
| `review required` | 需要人工或策略继续判断的候选数量。 |
| `safe cleanup token saving` | 只按安全清理候选估算的 token 节省比例，不代表真实 prompt token 已下降。 |

near-merge 专项结果是 `40` 个 case / `80` 行，`merge_suggestion_count = 40`，`review_required_count = 40`，`retained_protection = 100.0%`，`safe_cleanup_token_saving = 0.0%`。这说明 V3 保留了原始相似合并信号，但不把它计入安全清理收益。

V3 还新增 evaluator 侧 `source_ref` resolver 和 non-mutating dry-run patch：

- `source_fetch_mode = proxy|session-store`；formal synthetic V3 仍使用 proxy，因为合成 `source_ref` 不保证存在于真实 `sessions.db`。
- 单元测试覆盖 mapping resolver 和真实 `SessionStore.fetch_by_ids()`。
- dry-run patch 输出 `would_merge`、`would_mark_stale`、`would_remove_low_value`、`would_keep`、`requires_review`。
- patch 记录带 `writes_real_db = false`、`recoverability_status` 和 `recoverability_reason`，不写真实 memory DB。

因此记忆库卫生表后续不应只展示“重复合并率 / token 节省率”，还要展示两个安全指标：

```text
候选精度 = 正确候选数 / 实际候选数
关键记忆保护率 = 未被误伤的 retained 记忆数 / retained 记忆数
```

推荐把睡眠巩固的指标拆成三类：

| 指标组 | 用途 | 当前 V2 数据 |
| --- | --- | --- |
| cleanup recall | 证明该清理的东西能不能找出来 | hard `100.0%` |
| cleanup / candidate precision | 证明找出来的候选是否真的该动 | hard `75.0%` |
| retained protection | 证明关键记忆不会被误伤 | hard `90.0%` |

后续只有当 hard precision 和 retained protection 稳定后，才适合把 shadow 候选推进到 active dry-run patch。真实删除、合并或 supersede 还需要额外满足真实回源、可恢复和用户确认策略。

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

### 当前写入治理离线补强结果

Phase 6h/6j 的写入治理行只来自通用 target-metric shadow trace，候选规模较小，且容易出现“污染拦截率高，但有用候选是否被保留不清楚”的问题。Phase 6n 已经用独立写入治理计数评测补强这一点，当前正式写入治理离线报告见：

```text
my_md/memory_optimization/eval_reports/memory_write_governance_counts_eval.json
my_md/memory_optimization/eval_reports/memory_write_governance_counts_eval.md
```

这份报告使用 `1200` 个目标导向模板候选：

```text
common 600 + hard 600
6 类 * 每类 200 个候选
有用候选 400 个，污染/重复/冲突候选 800 个
```

基线是原本写入方式：`1200/1200` 全部写入。它的好处是有用候选 `400/400` 不会漏写，问题是污染、重复和冲突候选也会写入 `800/800`。

叠加写入价值治理、离线复核处理和最终写入安全门后：

- 第一阶段直接写入 `172/1200`，写入减少率 `85.6667%`。
- 第一阶段污染候选控制率 `97.25%`，直接拒绝误伤率 `0.0%`。
- 复核候选 `503` 条，复核后晋升写入 `253` 条。
- 最终写入 `400/1200`。
- 有用候选最终保留率 `400/400 = 100.0%`。
- 最终污染控制率 `800/800 = 100.0%`。
- 冲突复核保持率 `200/200 = 100.0%`。
- hard 重复泄漏率 `0/100 = 0.0%`。
- 严格理想差距总数从 `54` 降到 `0`。

这个结果可以替代旧的 `240` 候选写入治理 shadow 结论，用来说明离线写入治理规则已经覆盖“有用保留、污染控制、冲突复核、重复安全门”四个维度。但它仍然是离线模板集，不是真实线上采样。线上化时仍需要按本节 evidence schema 采集真实候选、真实决策、实际写入或复核结果和后续召回有用率。

### 当前写入治理线上 shadow 入口

Phase 6o 新增测试集驱动的写入治理线上 shadow runner：

```text
scripts/run_memory_write_governance_online_eval.py
```

它会把已标注写入治理候选穿过真实 `AgentLoop.process_direct()`，并可选调用真实 LLM；但候选和标签来自测试集，写入治理结果来自项目代码，不来自模型自评。默认使用 `skip_post_memory=True`，不写生产记忆库。

当前 fake-provider smoke 已跑通：

```text
candidate_count = 24
online_write_record_count = 24
real_llm_enabled = False
infra_passed = True
total_token_count = 720
avg_latency_ms = 34.5417
```

接入 `--online-write-evidence-json` 后，线上 evidence 行为：

| 指标 | before | after | 变化 |
| --- | ---: | ---: | ---: |
| 有效写入精度 | `33.3333%` | `100.0%` | `+66.6667` 个百分点 |
| 污染拦截率 | `0.0%` | `100.0%` | `+100.0` 个百分点 |
| 重复控制率 | `0.0%` | `100.0%` | `+100.0` 个百分点 |
| 冲突复核率 | `0.0%` | `100.0%` | `+100.0` 个百分点 |
| 写入减少率 | `0.0%` | `66.6667%` | `+66.6667` 个百分点 |
| 误拒率 | `0.0%` | `0.0%` | `0.0` 个百分点 |
| 误收率 | `100.0%` | `0.0%` | `-100.0` 个百分点 |

这仍然只是 fake-provider 在线路径验证，不是真实 LLM 结论。真实 LLM pilot 需要显式启用 `--enable-real-llm` 并保留 checkpoint。

真实 LLM pilot 已用同一批 `24` 个平衡候选跑通，随后又扩展到 `240` 个 common/hard 与类别双维度平衡候选。当前正式展示优先使用 `240` 条扩展样本，`24` 条 pilot 保留为链路验证历史。

```text
candidate_count = 240
online_write_record_count = 240
real_llm_enabled = True
infra_passed = True
provider_error_count = 0
timeout_count = 0
total_token_count = 1236228
avg_latency_ms = 2366.625
```

真实 LLM 扩展样本的 evidence 分布为：useful `80` 条全部 allow，pollution `80` 条全部 reject，duplicate `40` 条全部 reject，conflict `40` 条全部 review。接入 `--online-write-evidence-json` 后，target metrics 线上 evidence 行为：有效写入精度 `33.3333% -> 100.0%`、污染拦截率 `0.0% -> 100.0%`、重复控制率 `0.0% -> 100.0%`、冲突复核率 `0.0% -> 100.0%`、写入减少率 `0.0% -> 66.6667%`、误拒率 `0.0% -> 0.0%`、误收率 `100.0% -> 0.0%`。

这说明真实 LLM 接入后，测试集驱动的线上 shadow 链路和 evidence 转换是可用的。但它仍然不是生产流量评测，也不是 LLM 自动抽取候选记忆的评测；候选摘要和标签仍来自测试集，治理决策来自项目代码，且 `skip_post_memory=True` 阻止写入生产记忆库。

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
旧 target-metric trace: candidate_count = 240
Phase 6n 独立写入治理计数: candidate_count = 1200
原本写入基线 = 1200/1200
治理链路最终写入 = 400/1200
有用候选最终保留率 = 100.0%
最终污染控制率 = 100.0%
冲突复核保持率 = 100.0%
hard 重复泄漏率 = 0.0%
```

其中旧 `240` 候选 trace 行保留为历史 target-metric 口径；离线写入治理质量应看 Phase 6n 的 `1200` 候选离线计数报告。线上 shadow 质量现在优先看 Phase 6o 的真实 LLM `240` 条扩展 evidence：common/hard 各 `120`，6 类各 `40`，有效写入精度 `33.3333% -> 100%`，污染拦截率、重复控制率、冲突复核率均 `0% -> 100%`。`污染拦截率 before`、`重复控制率 before` 等没有真实 baseline 决策计数的离线字段会显示 `unavailable`，不再假写 0。

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
- 写入治理已经有测试集驱动的真实 LLM 线上 shadow evidence，但仍不代表生产自然流量、LLM 候选抽取质量或真实 DB 写入效果；睡眠巩固仍是 shadow / dry-run 指标，不代表真实 DB 已清理或真实 prompt token 已下降。
- 冲突链识别当前仅由一个 forked replacement chain 支撑，还需要更多分叉类型和回滚场景。

### 治理类指标和版本链审阅结论

| 模块 | 当前判断 | 问题 | 后续修订方向 |
| --- | --- | --- | --- |
| 重排与注入治理 | 相对合理 | 目标召回率没有提升，但错误召回率和错误注入率 after 都是 `0%`，说明它主要体现过滤和注入治理价值。 | 继续保留该指标，但后续补更多 forbidden / 相似干扰 case。 |
| 写入价值治理 | 离线写入阶段已补强，线上 shadow evidence 已有 240 条扩展样本 | Phase 6n 的 1200 候选离线计数已经验证最终有用保留 `100%`、最终污染控制 `100%`、冲突复核保持 `100%`、hard 重复泄漏 `0%`；Phase 6o 的 240 条真实 LLM shadow evidence 也验证了 provider 路径和 target metrics 输入。但这些仍来自测试集候选，不是生产自然流量。 | 继续补生产自然流量 evidence、LLM 自动候选抽取质量、真实写入结果、后续召回有用率、真实误拒率和误收率。 |
| 睡眠巩固 | 方向合理但仍是 shadow | token 节省率 after `33.482%`、召回保持率 after `100%` 是 dry-run 估算，不代表真实 DB 已清理或真实 prompt token 已下降。 | 补真实执行或线上 evidence：巩固前后 active 数、真实 prompt token、关键记忆保护率、巩固后真实召回准确率。 |
| 版本链与溯源 | 口径已修订且冲突链可测 | 当前有效版本召回率已经可解释，冲突链识别率 after 为 `100%`。 | 后续补更多冲突链类型和线上 evidence。 |

### 下一步计划

优先级仍然不是马上继续真实 LLM 长跑，而是先补齐离线指标剩余盲点：

1. 把 Phase 6n 的写入治理离线计数报告接入后续总览表，避免继续沿用旧 `240` 候选 shadow 口径。
2. 补睡眠巩固的真实 token / active 数 evidence 输入，区分 dry-run 估算和真实效果。
3. 扩展冲突链 fixture 类型，例如多层分叉、回滚分叉和跨 source_ref 分叉。
4. 再把已有 Phase 6e checkpoint 转成新版目标指标表；如果 checkpoint 仍不完整，再考虑恢复 provider 后续跑。

随后在真实 LLM 层复用 Phase 6e 的 checkpoint：

- 如果已有完整 checkpoint，就从 checkpoint 重建回答层目标指标报表。
- 如果 provider 余额恢复，用 `--resume` 补齐真实调用，再生成完整真实 LLM 目标指标报表。
- 写入治理和记忆库卫生的线上层需要额外 evidence 事件或 JSON 输入；没有这些事件时必须显示 unavailable。Phase 6n 已提供写入治理离线计数基准，但不能替代真实线上 evidence。

这样能保证：

- 先有稳定、可测试、可复现的报表结构。
- 再把真实 LLM 的不稳定性和成本放到 runner 层处理。
- 不把“provider 余额不足”误判成 memory 模块效果不好。
