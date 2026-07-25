# 记忆系统 Balanced 量化评测报告

本报告是离线确定性 trace 的分层代理评测，不调用真实 LLM，不读写真实 memory DB，不是生产回答准确率。

## 评测口径

- 样本规模：80 个目标导向 case，其中 common 40 个，hard 40 个。
- Balanced report 借鉴 RAG/Agent 分层评测共识，把回答、召回代理、证据、治理和效率分开；本项目的改进是把 memory 生命周期治理纳入评分，包括 forbidden、source_ref、版本链、scope 隔离和 token/sleep 信号。它仍然是离线代理评测，不是生产回答准确率。
- `retrieval_proxy_score` 是当前离线 trace 的召回代理指标，不是真实 `recall@k`。
- `efficiency_score` 缺失时保持 `unavailable`，计算 `balanced_score` 时只按可用维度归一化权重。
- `balanced_score = 0.30 * answer_score + 0.25 * retrieval_proxy_score + 0.20 * grounding_score + 0.15 * governance_score + 0.10 * efficiency_score; unavailable dimensions are omitted and remaining weights are normalized`

## 分层评分

| 指标 | 含义 | 方向 |
| --- | --- | --- |
| `answer_score` | 回答规则或目标记忆命中代理分，来自 `answer_rule_pass_rate` | 越高越好 |
| `retrieval_proxy_score` | 召回相关链路步骤上的离线召回代理分，不是真实 `recall@k` | 越高越好 |
| `grounding_score` | 来源、证据或可解释字段覆盖情况，来自 `memory_grounding_pass_rate` | 越高越好 |
| `governance_score` | 综合 forbidden 控制和 grounding 的治理分 | 越高越好 |
| `efficiency_score` | token 节省或 prompt token 控制的效率分；缺失时为 `unavailable` | 越高越好 |
| `balanced_score` | 只用可用维度归一化后的综合代理分 | 越高越好 |

## 链路 Balanced 增益

| step | label | balanced_score | 相邻增益 | answer_score | retrieval_proxy_score | grounding_score | governance_score | efficiency_score | available | unavailable |
| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | --- | --- | --- |
| chain_off | 关闭记忆增强 | 12.6923 | 0 | 0 | unavailable | 0 | 55 | unavailable | answer_score, grounding_score, governance_score | retrieval_proxy_score, efficiency_score |
| chain_write_value | 加入写入价值治理 | 45.8847 | 33.1924 | 73.336 | unavailable | 19.998 | 25.4975 | unavailable | answer_score, grounding_score, governance_score | retrieval_proxy_score, efficiency_score |
| chain_tri_retrieval | 加入三路召回 | 75.3243 | 29.4396 | 86.668 | 86.668 | 57.4983 | 57.4986 | unavailable | answer_score, retrieval_proxy_score, grounding_score, governance_score | efficiency_score |
| chain_graph_retrieval | 加入图谱召回 | 73.1838 | -2.1405 | 91.112 | 91.112 | 38.3321 | 53.9157 | unavailable | answer_score, retrieval_proxy_score, grounding_score, governance_score | efficiency_score |
| chain_rerank_injection | 加入重排与注入治理 | 68.594 | -4.5898 | 84.1877 | 84.1877 | 42.9993 | 61.6995 | 44.36 | answer_score, retrieval_proxy_score, grounding_score, governance_score, efficiency_score | none |
| chain_version_provenance | 加入版本链与溯源 | 67.0743 | -1.5197 | 79.8762 | 79.8762 | 44.1563 | 65.8345 | 44.36 | answer_score, retrieval_proxy_score, grounding_score, governance_score, efficiency_score | none |
| chain_sleep_consolidation | 加入睡眠巩固 | 67.2022 | 0.1279 | 73.0667 | 73.0667 | 49.4626 | 69.3518 | unavailable | answer_score, retrieval_proxy_score, grounding_score, governance_score | efficiency_score |
| chain_all_on | 全开组合校验 | 67.2022 | 0 | 73.0667 | 73.0667 | 49.4626 | 69.3518 | unavailable | answer_score, retrieval_proxy_score, grounding_score, governance_score | efficiency_score |

## common / hard 对比

| case_set | step | balanced_score | 相邻增益 | answer_score | retrieval_proxy_score | grounding_score | governance_score | efficiency_score |
| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | --- |
| common | chain_off | 12.6923 | 0 | 0 | unavailable | 0 | 55 | unavailable |
| common | chain_write_value | 45.8847 | 33.1924 | 73.336 | unavailable | 19.998 | 25.4975 | unavailable |
| common | chain_tri_retrieval | 74.9889 | 29.1042 | 86.668 | 86.668 | 57.141 | 55.9626 | unavailable |
| common | chain_graph_retrieval | 72.8074 | -2.1815 | 91.112 | 91.112 | 38.094 | 51.9751 | unavailable |
| common | chain_rerank_injection | 70.7297 | -2.0777 | 83.6448 | 83.6448 | 42.8564 | 59.9851 | 71.56 |
| common | chain_version_provenance | 69.3091 | -1.4206 | 79.3892 | 79.3892 | 44.0046 | 64.5875 | 71.56 |
| common | chain_sleep_consolidation | 66.6972 | -2.6119 | 72.6405 | 72.6405 | 49.2183 | 68.2105 | unavailable |
| common | chain_all_on | 66.6972 | 0 | 72.6405 | 72.6405 | 49.2183 | 68.2105 | unavailable |
| hard | chain_off | 12.6923 | 0 | 0 | unavailable | 0 | 55 | unavailable |
| hard | chain_write_value | 45.8847 | 33.1924 | 73.336 | unavailable | 19.998 | 25.4975 | unavailable |
| hard | chain_tri_retrieval | 75.6596 | 29.7749 | 86.668 | 86.668 | 57.8555 | 59.0344 | unavailable |
| hard | chain_graph_retrieval | 73.5601 | -2.0995 | 91.112 | 91.112 | 38.5703 | 55.8565 | unavailable |
| hard | chain_rerank_injection | 72.0224 | -1.5377 | 84.7306 | 84.7306 | 43.1422 | 63.414 | 72.8 |
| hard | chain_version_provenance | 70.4036 | -1.6188 | 80.3633 | 80.3633 | 44.308 | 67.0815 | 72.8 |
| hard | chain_sleep_consolidation | 67.7072 | -2.6964 | 73.4929 | 73.4929 | 49.707 | 70.4932 | unavailable |
| hard | chain_all_on | 67.7072 | 0 | 73.4929 | 73.4929 | 49.707 | 70.4932 | unavailable |

## 结论

- 关闭状态 balanced_score 为 `12.6923`。
- 全开组合 balanced_score 为 `67.2022`，相邻链路总提升 `54.5099` 分。
- 相邻增益最高的步骤是 `chain_write_value`，增益为 `33.1924` 分。
- 相邻增益最低的步骤是 `chain_rerank_injection`，变化为 `-4.5898` 分。
- 这个口径让后段治理、证据和效率模块有独立展示空间，但它仍然是离线代理评测，不能写成线上效果或真实准确率结论。
