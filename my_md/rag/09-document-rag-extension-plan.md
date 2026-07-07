# 09 Document RAG Extension Plan

这个文档用于记录后续为当前项目引入“文档检索增强 RAG”的学习、设计和实践计划。

当前项目已有的是个人长期记忆 RAG：围绕用户偏好、历史对话、行为规则、用户画像和事件记忆进行写入、召回、排序和注入。后续要练习的是另一类能力：面向项目文档、Markdown、PDF、网页资料、技术手册的 Document RAG。

## 一句话目标

```text
在不破坏现有 Agent Runtime 和 memory2 个人记忆系统的前提下，新增一个独立 Document RAG 子系统，用来锻炼文档加载、切块、召回、重排、引用、生成控制和评估能力。
```

## 为什么要单独做 Document RAG

现有 `memory2` 更像“个人记忆系统”，检索单元是结构化 memory item。

Document RAG 面对的是文档资料，检索单元通常是 chunk。

两者不应该混在一起：

| 方向 | 个人记忆 RAG | 文档 RAG |
| --- | --- | --- |
| 数据来源 | 对话、工具结果、用户偏好、用户事实 | Markdown、PDF、网页、项目文档、手册 |
| 最小检索单元 | memory item | document chunk |
| 核心问题 | 记住用户、纠错、失效、scope 隔离 | 切块、引用、覆盖率、忠实性 |
| 典型字段 | memory_type、summary、source_ref、status | doc_id、chunk_id、title、path、heading、page |
| 主要风险 | 错误记忆污染长期回答 | 召回不准、引用错误、文档幻觉 |

所以推荐新增独立模块，而不是把文档 chunk 塞进 `memory2.db`。

## 推荐技术路线

第一阶段建议：

```text
LlamaIndex + SQLite/sqlite-vec + 项目自研 ToolRegistry
```

边界：

- LlamaIndex 负责文档加载、切块、索引和基础 retriever。
- 项目自己的 AgentLoop、ToolRegistry、Plugin、Dashboard、Session 隔离继续保留。
- 文档检索能力通过工具暴露给 Agent。

推荐新增工具：

```text
search_docs(query, filters=None, top_k=None)
fetch_doc_chunk(chunk_id)
```

不建议第一阶段让 Document RAG 自动注入每一轮 prompt。先用工具方式接入，更可控，也更适合观察检索质量。

## 目标模块设计

建议新增模块结构：

```text
doc_rag/
  config.py          # RAG 参数配置
  loader.py          # 文档加载
  chunker.py         # 文档切块
  indexer.py         # embedding 与索引构建
  store.py           # chunk 元数据与向量存储
  retriever.py       # 检索入口
  reranker.py        # 可选重排
  citation.py        # 引用和来源格式化
  tools.py           # search_docs / fetch_doc_chunk 工具
  eval.py            # 离线评估
```

如果后续用插件方式接入，可以放到：

```text
plugins/document_rag/
```

## 第一阶段：基础文档 RAG

目标：先跑通最小闭环。

流程：

```text
文档目录 -> 加载 -> 切块 -> embedding -> 存储 -> search_docs 工具 -> Agent 引用回答
```

需要实现：

- 支持 Markdown 文档。
- 支持按标题和段落切块。
- 每个 chunk 保留 `doc_id`、`chunk_id`、`title`、`path`、`heading_path`。
- 支持向量召回 top_k。
- `search_docs` 返回 chunk 摘要、来源和分数。
- 回答中必须引用来源。

第一阶段重点参数：

```text
chunk_size
chunk_overlap
top_k
similarity_threshold
max_context_chars
```

阶段产出：

- 一个可搜索本项目文档的 `search_docs` 工具。
- 一份 20 条左右的测试问题集。
- 一份召回 trace 样例。

## 第二阶段：切块策略深入

目标：理解“怎么切”对 RAG 效果的影响。

需要比较的切块方式：

- 固定 token 切块。
- 按 Markdown 标题切块。
- 按段落切块。
- 标题 + 段落混合切块。
- 小 chunk 合并。
- 大 chunk 二次切分。

需要观察的问题：

- chunk 太小：语义不完整，回答缺上下文。
- chunk 太大：召回不准，注入成本高。
- overlap 太小：跨段信息断裂。
- overlap 太大：重复内容多，浪费 token。
- 不保留标题路径：召回片段缺少上下文。

建议记录参数实验：

| 实验 | chunk_size | chunk_overlap | 切块方式 | Recall@k | 问题 |
| --- | --- | --- | --- | --- | --- |
| A | 512 | 80 | 固定 token | 待填 | 待填 |
| B | 800 | 120 | 标题 + 段落 | 待填 | 待填 |
| C | 1000 | 150 | 语义段落 | 待填 | 待填 |

阶段产出：

- 一份切块实验记录。
- 一套适合本项目文档的默认切块参数。

## 第三阶段：检索前处理

目标：锻炼 query rewrite、query routing 和多查询召回能力。

需要设计：

- 判断是否需要查文档。
- 将用户问题改写成更适合文档检索的 query。
- 根据问题类型选择检索策略。
- 生成多个查询覆盖不同表述。
- 可选 HyDE：生成假想文档片段再检索。

问题类型可以先分成：

```text
概念解释
配置问题
代码流程
排错问题
API / 工具用法
架构设计问题
```

示例：

```text
用户问题：这个东西怎么配置？
改写后：项目中 Document RAG 的配置项、启用方式和默认参数说明
```

需要记录的参数：

```text
rewrite_enabled
multi_query_enabled
hyde_enabled
query_count
rewrite_timeout_ms
```

阶段产出：

- query rewrite prompt。
- query routing 规则。
- query rewrite 前后召回效果对比。

## 第四阶段：混合召回和重排

目标：理解 embedding 召回不是唯一方案。

建议实现：

```text
vector search
keyword search
metadata filter
RRF fusion
rerank
```

可练习的策略：

- 向量召回 top_k=20。
- 关键词召回 top_k=20。
- RRF 融合。
- reranker 取 top_n=5。
- 最终注入 3-5 个 chunk。

需要思考：

- 什么时候关键词比 embedding 更可靠？
- 什么时候 embedding 更适合？
- RRF 的权重如何调？
- reranker 的成本是否值得？
- metadata filter 应该在召回前还是召回后做？

建议参数：

```text
vector_top_k
keyword_top_k
rrf_k
keyword_weight
rerank_top_n
final_top_n
```

阶段产出：

- 一套 hybrid retrieval 配置。
- 一份 “vector only vs hybrid vs hybrid+rerank” 对比结果。

## 第五阶段：上下文注入和生成控制

目标：解决“召回到了不等于回答好”的问题。

需要控制：

- 最大注入 chunk 数。
- 最大注入字符数。
- 每个 chunk 最大长度。
- 是否按来源分组。
- 是否去重。
- 是否强制引用。
- 是否允许模型使用文档外知识。

推荐生成规则：

```text
1. 优先基于检索到的文档回答。
2. 文档没有明确依据时，要说“文档中未找到明确说明”。
3. 回答关键结论时给出来源。
4. 明确区分“文档明确说明”和“我的推断”。
5. 不要把个人 memory 和文档知识混为一谈。
```

需要记录的参数：

```text
max_chunks
max_context_chars
per_chunk_max_chars
require_citation
allow_model_prior
temperature
max_answer_tokens
```

阶段产出：

- 文档问答生成 prompt。
- citation 格式。
- 无答案场景处理规则。

## 第六阶段：评估体系

目标：让 RAG 优化有证据，而不是靠感觉。

评估集字段：

```text
question
gold_answer
expected_doc_id
expected_chunk_id
answerable
question_type
notes
```

核心指标：

- Recall@k：正确 chunk 是否被召回。
- MRR：正确 chunk 排名是否靠前。
- Context Precision：注入内容中相关内容占比。
- Faithfulness：回答是否忠于文档。
- Citation Accuracy：引用是否准确。
- No-answer Accuracy：文档没有答案时是否拒答。

最小评估流程：

```text
读取评估集
逐题 search_docs
记录召回 chunk
计算 Recall@k / MRR
生成回答
人工或 LLM 评估忠实性和引用
输出报告
```

阶段产出：

- `eval/doc_rag/questions.jsonl`
- `eval/doc_rag/run_eval.py`
- 一份评估报告 Markdown。

## 第七阶段：可观测性和 Dashboard

目标：让每次文档 RAG 行为可解释。

需要记录：

- 原始 query。
- rewrite 后 query。
- 是否使用 HyDE。
- vector hits。
- keyword hits。
- rerank hits。
- 最终注入 chunk。
- 最终回答引用。
- latency。
- token 使用。

Dashboard 可以增加：

```text
Doc RAG Trace
Doc Index Status
Chunk Browser
Eval Report
Failed Queries
```

阶段产出：

- 文档 RAG trace 数据结构。
- Dashboard 检索详情页。

## 第八阶段：权限、更新和工程化

目标：让文档知识库可以长期维护。

需要考虑：

- 哪些文档对哪些 session 可见。
- 文档更新后如何增量索引。
- 删除文档后如何删除 chunk。
- chunk_id 如何稳定。
- 同一文档多版本如何处理。
- 私有文档和公开文档如何隔离。
- 索引损坏如何重建。

建议字段：

```text
doc_id
version
source_path
content_hash
chunk_hash
indexed_at
updated_at
visibility_scope
```

阶段产出：

- 文档索引重建命令。
- 文档更新检测机制。
- 文档权限策略。

## 推荐学习问题清单

后续可以围绕这些问题继续深挖：

1. 文档 RAG 和当前 memory2 个人记忆 RAG 的边界是什么？
2. 为什么文档 RAG 不应该直接复用 memory2 的 memory_items 表？
3. Markdown 文档应该按标题切还是固定 token 切？
4. chunk_size 和 chunk_overlap 应该如何调参？
5. 为什么 chunk 必须保留 heading_path 和 source_path？
6. 文档检索应该用向量召回、关键词召回，还是 hybrid search？
7. RRF 融合解决什么问题？权重如何调？
8. query rewrite 什么时候会提升召回？什么时候会伤害召回？
9. HyDE 适合什么问题？为什么不能默认所有问题都开？
10. reranker 应该放在召回后哪一步？成本如何控制？
11. metadata filter 应该在召回前做还是召回后做？
12. 如何判断一个问题应该查文档、查个人记忆，还是直接回答？
13. search_docs 和 fetch_doc_chunk 为什么要分成两个工具？
14. 检索结果应该自动注入，还是由模型显式调用工具？
15. 文档问答如何避免幻觉？
16. 文档没有答案时应该如何拒答？
17. 引用应该引用 chunk、标题、文件路径还是页码？
18. 如何评估 Recall@k、MRR、Faithfulness 和 Citation Accuracy？
19. 如何把 RAG trace 做进 Dashboard？
20. 如果文档规模变大，什么时候从 sqlite-vec 切换到 Qdrant / Milvus？

## 面试表达角度

如果后续实现 Document RAG，可以这样表达：

```text
原项目已有个人长期记忆 RAG，但它服务的是用户偏好、历史事件和操作规则。为了补齐文档问答能力，我设计了独立的 Document RAG 子系统。它和个人记忆系统隔离，通过工具接入 Agent Runtime。这个模块重点练习文档加载、切块、embedding、hybrid retrieval、query rewrite、rerank、引用生成和离线评估。这样既保留了原项目自研 Agent Runtime 的架构优势，又能补齐企业知识库问答场景。
```

## 当前优先级

第一步先不要做太复杂。

推荐下一步：

```text
先实现 Markdown 文档 RAG 的最小闭环：
loader -> chunker -> indexer -> retriever -> search_docs tool -> citation answer
```

最小闭环完成后，再逐步加入：

```text
query rewrite
hybrid search
rerank
eval
dashboard trace
permissions
```

## 两周实现计划

如果目标是在两个星期内完成一版可展示能力，范围必须收缩。

两周内不建议同时把普通 Document RAG、GraphRAG、LLM Wiki 都做成完整版本。更合理的目标是：

```text
Document RAG 做扎实
GraphRAG 做轻量 MVP
LLM Wiki 做雏形页面生成
```

### 两周内必须完成

- Markdown 文档加载。
- 文档切块。
- embedding。
- 本地向量检索。
- `search_docs` 工具。
- `fetch_doc_chunk` 工具。
- 引用来源。
- 基础评估集。
- RAG trace 记录。

### 两周内可选完成

- query rewrite。
- hybrid search。
- rerank。

如果时间不足，优先级是：

```text
hybrid search > query rewrite > rerank
```

因为 hybrid search 能直接改善“关键词明确但 embedding 没命中”的问题，收益更稳定。

### 两周内轻量尝试

- 从文档中抽取模块、概念、工具、事件之间的简单关系，形成轻量 GraphRAG。
- 增加 `search_graph` 或 `find_related_modules` 原型工具。
- 自动生成 3-5 个 Wiki 页面，例如：
  - Agent Runtime
  - Memory 系统
  - Tool 系统
  - Proactive v2
  - Plugin 系统

### 14 天执行安排

| 时间 | 目标 |
| --- | --- |
| Day 1 | 明确 Document RAG 模块边界，设计表结构、配置项、工具接口 |
| Day 2 | 实现 Markdown loader 和基础 chunker |
| Day 3 | 实现 embedding 和本地向量存储 |
| Day 4 | 实现 `search_docs` 检索工具 |
| Day 5 | 实现 `fetch_doc_chunk` 和 citation 格式 |
| Day 6 | 接入 Agent ToolRegistry，能通过 CLI 问文档 |
| Day 7 | 做 20-30 条评估问题，跑 Recall@k / 命中检查 |
| Day 8 | 优化 `chunk_size`、`chunk_overlap`、`top_k`、`max_context_chars` |
| Day 9 | 加 query rewrite 或 hybrid keyword search，优先 hybrid |
| Day 10 | 增加 RAG trace，记录 query、hits、注入内容、引用 |
| Day 11 | 轻量 GraphRAG：抽取模块、文件、工具、事件之间的关系 |
| Day 12 | 实现 `search_graph` 或 `find_related_modules` 原型工具 |
| Day 13 | LLM Wiki 雏形：生成 3-5 个模块 Wiki 页面，保留来源引用 |
| Day 14 | 整理演示脚本、技术总结、面试表达和后续路线图 |

### 两周最终交付物

```text
1. 一个可用的 Document RAG 工具
2. 一份 RAG 参数配置
3. 一份评估集和评估结果
4. 一个轻量 GraphRAG 原型
5. 几个自动生成的 Wiki 页面
6. 一份面试讲稿：为什么这样设计，后续怎么演进
```

### 两周内的取舍规则

如果时间不够，砍掉顺序是：

```text
先砍 LLM Wiki
再砍 GraphRAG
不要砍 Document RAG 评估
```

原因：

- Document RAG 是底座。
- 评估能证明 RAG 效果，不应该砍。
- GraphRAG 是增强能力，可以先做轻量原型。
- LLM Wiki 是知识沉淀层，适合放到后续迭代。

### 两周目标的一句话版本

```text
两周内完成 Document RAG 扎实闭环，并做出 GraphRAG / LLM Wiki 的可演示雏形，而不是追求完整知识图谱和完整 Wiki 系统。
```

## RAG 中引入 LoRA 的学习方向

LoRA 可以和 RAG 结合，但定位必须清楚：

```text
RAG 负责知识
LoRA 负责行为
```

不推荐：

```text
把文档内容 LoRA 进模型，用 LoRA 替代 RAG
```

原因：

- 文档知识会更新，训练进模型后更新成本高。
- 模型记忆不方便引用来源。
- 模型内部知识难以删除、纠错和审计。
- 文档问答更需要原文证据和 citation。

推荐：

```text
用 LoRA 优化 RAG 中稳定、可评估的子任务。
```

### 适合 LoRA 的位置

#### 1. Query Rewrite LoRA

输入：

```text
用户问题 + 可选近期上下文
```

输出：

```text
更适合检索的 query
```

适合原因：

- 输入输出短。
- 格式稳定。
- 标注成本相对低。
- 评估可以直接看 Recall@k / MRR。
- 对召回效果影响明显。

示例：

```text
用户问题：这个怎么开？
上下文：正在讨论 proactive 配置
输出：proactive 功能的启用方式和配置项说明
```

这是最推荐的 LoRA 练习点。

#### 2. 文档问答格式 LoRA

输入：

```text
用户问题 + 检索到的文档片段
```

输出：

```text
带引用、先结论、再步骤、无依据拒答的回答
```

适合训练：

- 回答格式稳定。
- 强化 citation。
- 训练“文档没有依据就拒答”。
- 减少生成层自由发挥。

注意：

```text
这只能优化生成层行为，不能替代文档检索。
```

#### 3. RAG 路由 LoRA

输入：

```text
用户问题
```

输出：

```text
查文档 / 查个人记忆 / 直接回答 / 调工具
```

适合训练：

- 问题分类。
- RAG 路由。
- 工具选择前置判断。
- 降低无效检索。

#### 4. Rerank LoRA

理论上可以训练：

```text
query + chunk -> relevant / irrelevant
```

但不建议第一阶段做。

原因：

- 数据标注成本更高。
- 训练和评估更复杂。
- 可以先用现成 reranker 或规则评估替代。

### 推荐最小实验：Query Rewrite LoRA

如果后续要在 RAG 中体现 LoRA，建议只做一个小而完整的实验：

```text
Query Rewrite LoRA
```

完整闭环：

```text
收集问题
-> 标注理想检索 query
-> 训练小模型 LoRA
-> 接入 Document RAG 的 query rewrite 层
-> 对比 LoRA 前后 Recall@k / MRR
```

### 数据集设计

最小实验数据量：

```text
100-300 条样本：跑通流程
500-1000 条样本：开始有观察价值
2000+ 条样本：效果更稳定
```

样本格式：

```json
{
  "instruction": "将用户问题改写为适合文档检索的 query",
  "input": "这个怎么开？上下文：正在讨论 proactive 配置",
  "output": "proactive 功能的启用方式和配置项说明"
}
```

可以从这些来源构造样本：

- 文档 RAG 评估集。
- 用户真实提问。
- `search_docs` 失败案例。
- query rewrite 前后召回差距大的案例。
- LLM 生成初稿 + 人工修正。

### 评估方式

不要只看 LoRA 生成的 query “像不像”。

应该看它是否提升检索效果：

```text
Rewrite 前 Recall@k
Rewrite 后 Recall@k
Rewrite 前 MRR
Rewrite 后 MRR
无答案问题误召回率
query rewrite 延迟
```

推荐对比：

```text
原始 query
规则 rewrite
LLM rewrite
LoRA rewrite
```

### 对电脑性能的要求

LoRA 训练仍然吃 GPU。

如果本机没有 12GB+ 显存，不建议本地训练。可以采用：

```text
本地做数据集、评估、接入逻辑
云 GPU 做 LoRA 训练
本地加载训练后的 adapter 或继续走云端推理
```

两周主线中，LoRA 不应作为第一优先级。

推荐节奏：

```text
先完成 Document RAG
再记录 query rewrite 数据
最后做 Query Rewrite LoRA 实验
```

### 面试表达

可以这样讲：

```text
我没有用 LoRA 记文档知识，因为文档更新频繁，应该走 RAG。LoRA 只用于优化 RAG 中稳定、可评估的行为子任务，比如 query rewrite。具体做法是收集用户问题和理想检索 query，训练一个小模型 LoRA，然后接入检索前处理层，最后用 Recall@k 和 MRR 对比微调前后的召回质量。
```

## Agent Gateway 学习方向

当前项目里需要区分两类“网关”。

### 当前现状

#### 1. 被动对话链路没有独立 Agent Gateway

当前用户消息入口不是一个统一的 HTTP/API Gateway，而是：

```text
CLI / Telegram / QQ / QQBot channel adapter
-> InboundMessage
-> MessageBus
-> AgentLoop
-> OutboundMessage
-> MessageBus
-> channel adapter 发回用户
```

也就是说，当前被动对话链路主要靠：

- channel adapter 适配不同平台。
- `InboundMessage / OutboundMessage` 统一消息格式。
- `MessageBus` 做异步消息流转。
- `AgentLoop` 消费消息并生成回复。

从架构意义上看，`MessageBus` 承担了部分“消息网关”职责，但它还不是完整的 Agent Gateway。

#### 2. 主动链路有 DataGateway

项目中存在 `proactive_v2/gateway.py`，里面的 `DataGateway` 用于主动链路。

它的职责是：

```text
alerts / context / content feed
-> 并行预取
-> content 提前 web_fetch
-> 生成 GatewayResult
-> proactive agent tick 使用这份输入快照
```

这个 `DataGateway` 是“主动 Agent 的数据预取网关”，不是所有用户请求的统一入口网关。

### 当前缺少的完整 Agent Gateway 能力

如果从生产级 Agent 应用角度看，一个真正的 Agent Gateway 通常还需要：

```text
统一认证
限流
请求校验
消息去重
幂等请求 id
多租户 / 多用户隔离
权限策略
路由到 session
统一 trace id
请求审计
错误标准化
熔断和降级
```

当前项目的 channel adapter 和 MessageBus 已经解决了多渠道消息接入，但还没有把上述能力抽成独立 Gateway 层。

### 后续可新增 AgentGateway 模块

如果后续想学习 Agent 工作流和工程化网关，可以新增：

```text
agent/gateway/
  request.py       # 标准化请求对象
  response.py      # 标准化响应对象
  gateway.py       # AgentGateway 主入口
  policies.py      # 鉴权、限流、路由策略
  idempotency.py   # 幂等请求处理
  audit.py         # 请求审计
```

目标链路：

```text
channel adapter / HTTP API
-> AgentGateway
-> 校验 / 鉴权 / 限流 / 去重 / trace_id
-> InboundMessage
-> MessageBus
-> AgentLoop
```

### 为什么这个方向值得学习

Agent Gateway 能帮助理解真实 Agent 应用从 Demo 到生产的差异：

- Demo 只需要把消息送进 AgentLoop。
- 生产系统需要知道谁发来的、有没有权限、是否重复、是否超限、如何审计、如何追踪。
- 多渠道 Agent 如果没有统一入口治理，很容易出现 session 污染、权限混乱、消息重复和排障困难。

### 面试表达

可以这样讲：

```text
当前项目的被动对话链路没有独立 Agent Gateway，而是由 channel adapter 把 CLI、Telegram、QQ 等平台消息统一成 InboundMessage，再通过 MessageBus 进入 AgentLoop。MessageBus 起到了部分消息网关作用，但它还不包含认证、限流、幂等、审计和统一 trace 等生产级网关能力。项目里的 DataGateway 主要服务 proactive 主动链路，用于并行预取 alerts、context 和 content feed。后续如果产品化，我会新增 AgentGateway 层，把多渠道入口的鉴权、限流、去重、路由、trace 和审计统一收敛起来。
```

## 维护规则

后续每次推进 Document RAG，都需要更新本文档：

- 新增设计决策。
- 新增参数实验。
- 新增评估结果。
- 新增失败案例。
- 新增面试表达。

提示词：

```text
请根据本次 Document RAG 的实现/实验/讨论，更新 my_md/rag/09-document-rag-extension-plan.md，补充设计决策、参数选择、评估结果、失败案例和面试表达。
```
