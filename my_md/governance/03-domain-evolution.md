# Domain Evolution

这个文档统一记录各领域的演进过程：发现了什么、做了什么、得到了什么结果、下一步怎么推进。

它替代原先分散在各领域目录下的演进记录，把 Architecture、Test、RAG、System 的过程记录集中到一个入口。

## 使用规则

- 原始事实仍保留在产生它的目录，例如测试报告留在 `test_docs/eval_suite/reports/`。
- 领域过程记录统一写在本文档，按 Architecture / Test / RAG / System 分节。
- 需要进入全局问题治理的问题，同步到 `01-issue-index.md` 和 `02-current-issues.md`。
- 形成完整闭环、适合面试复盘的问题，同步到 `06-star-log.md`。

## 记录模板

### DOMAIN-xxx: 标题

领域：

- Architecture / Test / RAG / System

场景：

-

发现：

-

处理：

-

结果：

-

证据：

-

影响：

-

下一步：

-

关联文档：

-

## Architecture

### ARCH-001: 从测试失败中识别三个核心架构改进点

场景：

- 查看深度自动评估报告后，分析 22 个失败 case 的真实原因。

发现：

- 临时 session 信息可能被写入长期记忆，导致跨 session 看似泄漏。
- 用户明确要求“不用工具”时，模型仍可能调用工具。
- 简单任务可能触发过长工具链，导致成本和延迟上升。

处理：

- 暂不直接修改核心源码。
- 先把测试误判、judge 基础设施问题和真实 agent 行为问题分开。
- 将核心改进方向记录到 governance 体系中。

结果：

- 明确了后续架构修复顺序：记忆写入边界 -> no-tool 硬约束 -> 工具链成本控制。

证据：

- `my_md/governance/02-current-issues.md`
- `my_md/governance/04-fix-roadmap.md`
- `my_md/governance/06-star-log.md`

影响：

- 后续修改 `agent/`、`plugins/`、`memory2/` 前，先有明确问题边界和验证目标。

下一步：

- 等测试误判修正后，再进入核心源码修复。

关联文档：

- `my_md/governance/01-issue-index.md`
- `my_md/governance/04-fix-roadmap.md`

## Test

### TEST-001: deep live eval 首轮报告暴露测试噪声

场景：

- 运行 `python3 my_md/test_docs/eval_suite/deep_live_eval_runner.py --judge` 后查看结果。

发现：

- 102 条 safe case 中 pass 80、fail 22。
- judge 全部 skipped，原因是当前环境缺少 `openai` Python 包。
- 部分失败是测试断言过硬，不是 agent 行为错误。

处理：

- 将测试噪声记录到 governance。
- 第一阶段计划先修测试集和 judge runner，不先改 agent 核心源码。

结果：

- 明确了测试体系下一步：修 group-level 工具断言、放宽中文同义表达、修 judge 依赖。

证据：

- `my_md/test_docs/eval_suite/reports/deep-live-report-2026-07-03-155850-236591.md`
- `my_md/governance/02-current-issues.md`

影响：

- 后续报告中的失败项会更接近真实系统行为问题。

下一步：

- 小范围回归 A019、C011、C014、D015、D024。
- 验证 judge 不再全部 skipped。

关联文档：

- `my_md/governance/04-fix-roadmap.md`
- `my_md/governance/06-star-log.md`

### TEST-002: EV-001 第一阶段测试输入消歧义检查

场景：

- 针对 EV-001“临时 session 信息可能被写入长期记忆”，先执行第一阶段方案：检查并修正测试输入，避免测试本身诱导模型写入长期记忆。

发现：

- `deep-live-eval-cases.yaml` 中主要声明型 session 临时事实已经带有“临时会话信息，不要写入长期记忆”前缀。
- 未带该前缀的 `EVAL_SESSION_*` 多数是查询句、预期字段或非声明型任务，不属于需要写入长期记忆的临时事实声明。

处理：

- 暂未继续修改 YAML 内容。
- 对重点 case 做 dry-run 校验，确认测试集仍能正常展开。

结果：

- `DL-A001`、`DL-B001`、`DL-B-010`、`DL-B-012`、`DL-B-018`、`DL-B-021`、`DL-B-023` dry-run 均无结构性问题。

证据：

- `python3 my_md/test_docs/eval_suite/deep_live_eval_runner.py --dry-run --case DL-A001 --case DL-B001 --case DL-B-010 --case DL-B-012 --case DL-B-018 --case DL-B-021 --case DL-B-023`
- 生成报告：`my_md/test_docs/eval_suite/reports/deep-live-report-2026-07-03-172053-787002.md`

影响：

- 方案 1 已基本完成，后续如果仍发生临时记忆写入，更可能是模型/tool 层问题，而不是测试输入歧义。

下一步：

- 进入方案 2 或方案 3：强化系统提示词，或在 `memorize` 工具层增加硬拦截。

关联文档：

- `my_md/governance/01-issue-index.md`
- `my_md/governance/02-current-issues.md`
- `my_md/governance/04-fix-roadmap.md`

### TEST-003: EV-001 小范围 live 回归暴露 fetch_messages 跨 session 线索

场景：

- 在完成 session 临时事实输入消歧义检查后，运行 7 条重点 case 的 live 回归。

发现：

- 总计 7 条 case，pass 5，fail 2。
- `DL-B-012` 失败：cli_b 回答中包含了 cli_a 的 `value-a-012`。
- `DL-B-023` 失败：cli_b 回答了 cli_a 的 `private-a-b023`。
- `DL-B-018` 虽然 pass，但调用了 `fetch_messages`、`forget_memory`、`memorize`，说明临时 session 信息仍可能触发记忆工具链。

处理：

- 暂未修改核心代码。
- 将问题从单一“长期记忆污染”扩展为两个待定位方向：记忆工具触发边界、消息回源工具 session 隔离。

结果：

- 方案 1 只能确认测试输入已经较清楚，不能解决真实隔离问题。
- 新增 EV-006：`fetch_messages` 可能跨 session 回源到其他会话内容。

证据：

- 报告：`my_md/test_docs/eval_suite/reports/deep-live-report-2026-07-03-172519-006985.md`
- JSON：`my_md/test_docs/eval_suite/reports/deep-live-report-2026-07-03-172519-006985.json`

影响：

- 后续不能只修改 `memorize`，还必须检查 `fetch_messages` / `search_messages` 的 session 过滤逻辑。
- 需要确认 eval runner 的 `cli_a/cli_b/cli_c` 是否真的隔离 session key。

下一步：

- 检查 `fetch_messages` 工具实现和 source_ref 来源。
- 检查 runner 中多 channel/session 的构造方式。
- 再决定是否在工具层增加 session 范围校验。

关联文档：

- `my_md/governance/01-issue-index.md`
- `my_md/governance/02-current-issues.md`
- `my_md/governance/06-star-log.md`

### TEST-004: 审查 eval runner 的多 session 隔离逻辑

场景：

- 针对 `DL-B-012`、`DL-B-023` 中出现的跨 session 内容泄漏，先排查测试 runner 是否真的为 `cli_a`、`cli_b`、`cli_c` 建立了不同会话。

发现：

- `deep_live_eval_runner.py` 中 `run_case()` 使用 `clients: dict[str, IpcClient]` 按 step 的 `channel` 缓存 client。
- 同一个 case 内，相同 channel 复用同一个 `IpcClient`，不同 channel 会创建不同 `IpcClient`。
- `IpcClient.ask()` 发送的 payload 只有 `content`，不显式传 session；session 由 IPC 服务端按连接生成。
- `infra/channels/ipc_server.py` 中每个连接用 `chat_id = f"cli-{id(writer)}"` 生成独立 chat_id。
- 最新 report JSON 中，`cli_a`、`cli_b`、`cli_c` 的 `session_key` 确实不同。

处理：

- 对照最新 report JSON 检查每个 step 的 `channel` 和 `turn.session_key`。
- 核对 IPC server 的连接到 chat_id 生成逻辑。

结果：

- runner 侧 session 隔离基本成立。
- `DL-B-012` 中 cli_a 为 `cli:cli-133349980691648`，cli_b 为 `cli:cli-133350009947648`。
- `DL-B-023` 中 cli_a 为 `cli:cli-133350003869072`，cli_b 为 `cli:cli-133350003870864`。
- 因此，跨 session 内容泄漏更可能发生在 `fetch_messages/search_messages`、source_ref 注入或记忆工具链，而不是 runner 复用了同一 session。

证据：

- `my_md/test_docs/eval_suite/deep_live_eval_runner.py`
- `infra/channels/ipc_server.py`
- `my_md/test_docs/eval_suite/reports/deep-live-report-2026-07-03-172519-006985.json`

影响：

- 下一步排查重点从测试 runner 转向消息回源工具和 source_ref 来源。

下一步：

- 审查 `agent/tools/message_lookup.py` 中 `FetchMessagesTool` 和 `SearchMessagesTool` 的 session 过滤逻辑。
- 查看失败 turn 的 `fetch_messages` 参数，确认 source_ref 从哪里来。

关联文档：

- `my_md/governance/02-current-issues.md`
- `my_md/governance/06-star-log.md`

### TEST-005: 审查 message_lookup 工具的 session 过滤逻辑

场景：

- 在确认 eval runner 的 `cli_a`、`cli_b`、`cli_c` 基本使用不同 session 后，继续排查 `DL-B-012`、`DL-B-023` 的跨 session 内容来源。

发现：

- `FetchMessagesTool` 当前只根据 `ids/source_ref/source_refs` 查询消息，没有接收或校验当前 `session_key`。
- `SearchMessagesTool` 有可选 `session_key` 参数，但模型不传时会变成全局历史搜索。
- 工具上下文同步阶段没有注入完整 `session_key`，只注入了 `channel`、`chat_id` 和 `current_user_source_ref`。
- store 层 `fetch_by_ids()` 是按消息 id 全局读取；`fetch_by_ids_with_context()` 会按 source_ref 自带的 session 扩展上下文。

处理：

- 暂未改动源代码。
- 将问题归入 EV-006：消息回源工具默认全局能力导致 session 隔离风险。
- 明确后续修复方向：工具上下文注入当前 session，搜索默认当前会话，回源默认当前会话，跨 session 证据回源走显式授权路径。

结果：

- runner 侧隔离问题基本排除后，`message_lookup.py` 成为当前最明确的代码层风险点。
- `fetch_messages` 跨 session 不是偶发测试问题，而是当前工具设计允许的行为。

证据：

- `agent/tools/message_lookup.py`
- `agent/lifecycle/phases/before_reasoning.py`
- `agent/tools/registry.py`
- `session/store.py`

影响：

- 后续修复 EV-006 时，不能只改测试用例或 prompt，需要考虑工具默认权限边界。
- 同时要避免破坏长期记忆回源能力，因此跨 session source_ref 是否允许需要单独设计。

下一步：

- 查看失败 turn 的 `fetch_messages` 参数，确认 source_ref 是来自长期记忆、搜索结果、历史提示还是模型自行构造。
- 设计最小修复：默认当前 session，必要时提供显式全局查询能力。
- 增加单元测试覆盖跨 session fetch/search 的默认隔离行为。

关联文档：

- `my_md/governance/02-current-issues.md`
- `my_md/governance/06-star-log.md`

### TEST-006: 对失败 turn 的 source_ref 来源做实证排查

场景：

- 在确认 `message_lookup.py` 存在默认全局回源风险后，继续检查 `DL-B-012` 和 `DL-B-023` 的实际 `fetch_messages` 参数，区分“工具执行层跨 session”和“回答层混入其他上下文”。

发现：

- `DL-B-012` 对应 turn `333`，当前 session 是 `cli:cli-133350009947648`。
- turn `333` 的 `fetch_messages` 参数是 `source_ref=cli:cli-133350009947648:0`，属于 cli_b 当前 session。
- 该工具结果只返回了 cli_b 的 `value-b-012`，没有返回 cli_a 的 `value-a-012`。
- 当前 cli_b session history 中没有 `value-a-012`。
- memory2 中存在 active 记忆 `e5f2dd96b17d | EVAL_SESSION_B012 的 A 变量是 value-a-012`。
- `recall_inspector.jsonl` 记录该 A 变量记忆被作为“相关历史”注入 prompt，因此 `DL-B-012` 的 A 值来源是长期记忆自动注入。
- `DL-B-023` 对应 turn `342`，当前 session 是 `cli:cli-133350003870864`。
- turn `342` 的 `fetch_messages` 参数是 `source_ref=cli:cli-133349980688512:2`，属于另一个旧 session，内容包含 `private-a-b023`。
- 当前 cli_b session 实际只有查询问题，没有说过 `private-a-b023`。
- `rag_queries` 和 `memory_writes` 中未查到与 `DL-B-023/private-a-b023` 对应的记录，暂不能证明 source_ref 来自长期记忆或 RAG。

处理：

- 暂未修改源代码。
- 将两个失败 case 分开归因：
  - `DL-B-012`：临时 session 数据被写入长期记忆，并通过自动记忆上下文注入到后续 prompt。
  - `DL-B-023`：明确是工具允许跨 session source_ref 回源。

结果：

- EV-001 和 EV-006 的边界更清晰：
  - `DL-B-012` 属于 EV-001：长期记忆污染导致跨 session 信息进入 prompt。
  - `DL-B-023` 属于 EV-006：`fetch_messages` 缺少当前 session guard。
- 修复优先级调整为：先修长期记忆写入边界并清理污染记忆，再修 `fetch_messages/search_messages` 的 session 边界。

证据：

- observe DB：`/home/jjh/.akashic/workspace/observe/observe.db`
- sessions DB：`/home/jjh/.akashic/workspace/sessions.db`
- memory2 DB：`/home/jjh/.akashic/workspace/memory/memory2.db`
- recall inspector：`/home/jjh/.akashic/workspace/observe/recall_inspector.jsonl`
- 最新报告：`my_md/test_docs/eval_suite/reports/deep-live-report-2026-07-03-172519-006985.json`

影响：

- 不能把所有 session isolation 失败都归为同一种原因。
- 后续修复需要同时覆盖工具执行层安全和回答层上下文污染。

下一步：

- 设计并实现 `fetch_messages` 默认当前 session 限制。
- 设计并实现 `search_messages` 默认当前 session 限制。
- 设计并实现临时 session 信息不进入 memory2 的写入边界。
- 清理已有 `EVAL_SESSION_*` 污染记忆后做小范围回归。

关联文档：

- `my_md/governance/02-current-issues.md`
- `my_md/governance/06-star-log.md`

## RAG

### RAG-001: 确定 Document RAG 的学习与实现路线

场景：

- 讨论如何在当前项目中锻炼 RAG 能力，并区分普通 Document RAG、GraphRAG、LLM Wiki、LoRA/RAG。

发现：

- 当前项目已有个人长期记忆 RAG，但没有独立的文档检索增强 RAG。
- 个人 memory RAG 和 Document RAG 的数据来源、召回目标、评估指标不同。

处理：

- 规划独立 Document RAG 子系统。
- 先做普通文档 RAG，再演进到 hybrid search、query rewrite、rerank、GraphRAG 和 LLM Wiki。
- 将 LoRA 放在 query rewrite 等稳定子任务上，而不是用来记文档知识。

结果：

- 形成两周实现路线和相关设计文档。

证据：

- `my_md/rag/09-document-rag-extension-plan.md`
- `my_md/rag/10-document-rag-design.md`
- `my_md/rag/11-document-rag-implementation-plan.md`

影响：

- 后续 RAG 实现可以围绕可评估指标推进，而不是只做功能演示。

下一步：

- 开始 Document RAG 最小闭环：loader、chunker、indexer、retriever、search_docs 工具、评估集。

关联文档：

- `my_md/rag/12-document-rag-params-experiments.md`
- `my_md/rag/13-document-rag-evaluation.md`

### RAG-002: Document RAG 接入 Agent 工具链

场景：

- P4-P6 已完成文档索引、向量检索和 trace 后，继续把 Document RAG 暴露给 Agent 可调用工具。

发现：

- 后端检索已经能稳定命中测试语料，但还不能被 Agent 在对话中直接使用。
- 文档检索和个人长期记忆检索必须保持工具边界清晰，避免文档问题误走 `recall_memory`。
- Agent 可发现工具后，仍可能选择通用文件读取工具展开证据，而不是专门的 chunk 展开工具。

处理：

- 新增 `search_docs` 和 `fetch_doc_chunk` 两个只读工具。
- 新增 `doc_rag` toolset，并接入默认 ToolRegistry wiring。
- `search_docs` 返回 snippet、source_path、heading_path、chunk_id、score 和 trace_id，不返回完整 chunk 内容。
- `fetch_doc_chunk` 按 chunk_id 返回 capped content，并标记是否截断。
- 工具在 `doc_rag.enabled=false` 时仍注册，但执行时返回结构化 `doc_rag_disabled`。
- 使用临时配置启用 Document RAG 完成 CLI smoke，不改动项目 `config.toml`。

结果：

- Doc RAG 测试矩阵通过：`58 passed, 1 warning`。
- 既有 memory/tool discovery 回归通过：`16 passed, 1 warning`。
- black check 和 compileall 均通过。
- 真实 Agent CLI smoke 中，Agent 通过 `tool_search` 解锁并调用 `search_docs`，未调用 `recall_memory`。
- `search_docs` 返回 `trace_id=90eaa095ed4940f3912cc969de9f6e31`，top1 命中 `my_md/doc_rag_corpus/manual_test.md > Agent Runtime`。

证据：

- `my_md/rag/11-document-rag-implementation-plan.md`
- `my_md/rag/17-document-rag-p7-tools-plan.md`
- `~/.akashic/workspace/doc_rag/retrieval_traces.jsonl`

影响：

- Document RAG 已从脚本级能力进入 Agent 工具调用链。
- 后续可以开始做 citation 规则和 e2e 评估，而不是继续停留在后端检索验证。

下一步：

- P9：设计并实现文档回答引用规则，引导需要展开证据时优先使用 `fetch_doc_chunk`。
- P10：设计 retrieval-only 和 Agent e2e 评估，覆盖召回、工具路径、引用和忠实度。

关联文档：

- `my_md/rag/10-document-rag-design.md`
- `my_md/rag/13-document-rag-evaluation.md`

### RAG-003: P9 citation 计划审阅后升级为一步到位方案

场景：

- 在准备实现 P9 Document RAG citation 前，对 `18-document-rag-p9-citation-plan.md` 做逻辑审阅。

发现：

- 原计划说能防止假引用，但轻量 guard 只能追加真实引用，不能识别和移除模型编造的 `[fake.md > Fake]`。
- 原计划会在 tool chain 中出现 `search_docs` 时追加引用，可能给“没有足够文档证据”的拒答错误补引用。
- 原计划的 no-fake-citation 验收只覆盖 no hits，不覆盖“回答里已有假 citation”的场景。
- 原计划无条件注入 Document RAG 引用规则，`doc_rag.enabled=false` 时会增加提示噪声。

处理：

- 将 P9 目标从“轻量引用 guard”升级为“Document RAG citation validator”。
- 计划新增 `PluginContext.app_config`，让插件能读取全局 `Config`，并只在 `doc_rag.enabled=true` 时注入 Document RAG 引用规则。
- 计划要求 validator 从当前轮 `search_docs` / `fetch_doc_chunk` 工具结果构造 `allowed_citations`。
- 计划要求最终回答中不在 `allowed_citations` 内的文档引用被移除，并记录到 `ctx.outbound_metadata["doc_rag_citation"]`。
- 计划要求无证据回答和 `hit_count=0` 场景不追加引用。

结果：

- P9 计划已经记录当前问题、一步到位解决方案、任务拆分、测试用例和验收标准。
- P9 执行范围扩大，但仍不改 AgentLoop，不改检索排序，不混用 memory citation 协议。

证据：

- `my_md/rag/18-document-rag-p9-citation-plan.md`
- `my_md/rag/11-document-rag-implementation-plan.md`

影响：

- P9 不只是让答案“带引用”，还要让文档引用具备可校验性。
- P10 评估可以直接消费 validator 输出的 `allowed_citations`、`removed_fake_citations`、`inserted_fallback` 等字段。

下一步：

- 按 P9 修订计划执行：先实现 `PluginContext.app_config`，再实现工具 citation 字段，最后实现 citation validator 和 CLI smoke。

关联文档：

- `my_md/rag/10-document-rag-design.md`
- `my_md/rag/13-document-rag-evaluation.md`

### RAG-004: P9 Document RAG 引用校验已完成自动化闭环

场景：

- P7/P8 已经让 Agent 能通过 `tool_search -> search_docs` 使用 Document RAG，但最终回答还缺少可校验引用，且模型可能编造 `[fake.md > Fake]` 这类文档引用。

发现：

- 仅靠 prompt 不能保证引用真实。
- 仅追加引用不能处理模型已经生成的假引用。
- `doc_rag.enabled=false` 时不应该注入 Document RAG 引用规则。
- 普通 markdown 文本如 `[README.md]` 不应被误识别为 Document RAG citation。

处理：

- `search_docs` 和 `fetch_doc_chunk` 输出中新增 `citation` 字段。
- 工具描述和 search hint 增加 citation 与 `fetch_doc_chunk` 展开证据指引。
- `PluginContext` 新增 `app_config`，插件可以读取全局 `Config`，但不污染插件本地 `config`。
- `plugins/citation` 增加 Document RAG citation validator，从当前轮工具结果构建 allowlist，移除未知文档引用，缺引用时追加真实来源，无证据回复不追加引用。
- 引用识别规则收窄为 `[xxx.md > heading]`，避免误删普通 markdown 文件名。

结果：

- Document RAG citation 从“提示词约束”提升为“工具结果 allowlist + after-reasoning 校验”。
- 记忆引用协议 `§cited:[id]§` 与 Document RAG 可见引用 `[source_path > heading_path]` 保持隔离。
- 自动化验证通过：Document RAG、citation、plugin manager、memory2 baseline、tool discovery 共 `135 passed`；black check 和 compileall 通过。

证据：

- `my_md/rag/18-document-rag-p9-citation-plan.md`
- `plugins/citation/plugin.py`
- `tests/test_doc_rag_citation_plugin.py`
- `tests/test_citation_plugin.py`

影响：

- 后续 P10 可以直接评估 `citation_missing`、`citation_fake`、`no_evidence_failed` 等失败类型。
- 当前自动测试已证明 citation 机制可校验，但还需要真实 CLI/LLM smoke 验证模型在实际对话中是否自然使用 `fetch_doc_chunk` 和 citation。

下一步：

- 执行 P9 CLI/LLM smoke。
- 进入 P10 评估 runner，建立 retrieval-only 和 agent e2e 的可重复评估。

关联文档：

- `my_md/rag/11-document-rag-implementation-plan.md`
- `my_md/rag/18-document-rag-p9-citation-plan.md`

### RAG-005: P9 live smoke 发现 Document RAG 未启用与 disabled fallback 问题

场景：

- P9 citation validator 已完成自动化验证后，进入真实 CLI/LLM smoke。
- 用户提问：`请从文档知识库中检索agent runtime负责什么？回答必须带文档引用`。

发现：

- Agent 能通过 `tool_search` 找到 `search_docs` / `fetch_doc_chunk`，说明工具注册和工具发现生效。
- Agent 调用了 `search_docs`，但返回 `doc_rag_disabled`。
- 当前 `config.toml` 未配置 `[doc_rag]`，实际 `doc_rag.enabled=false`。
- 索引库本身正常：`doc_rag.db` 中已有 11 个 ready chunks。
- 模型在 `doc_rag_disabled` 后继续使用 `list_dir` / `read_file` 组织答案，最终没有 Document RAG citation。

处理：

- 将该问题登记为 `RAG-005`。
- 明确短期处理是启用 `[doc_rag] enabled=true` 并重启 Agent 后重跑 P9 smoke。
- 明确中期优化是增强 disabled 工具返回和工具描述，要求模型在 disabled 场景停止并提示启用配置，而不是 fallback 到 `read_file`。

结果：

- 当前 P9 自动化闭环仍然有效，但真实 live smoke 未通过。
- 失败原因被定位为运行配置未启用 Document RAG，以及 disabled 场景工具治理不足。
- 2026-07-11 已完成第一阶段修复：增强 `doc_rag_disabled` 工具返回协议，并补充工具描述与回归测试。
- 第一阶段没有改 AgentLoop；它依赖模型遵循工具结果语义，不是执行器级硬阻断。

证据：

- `observe.db` turn id `344`
- `search_docs` 结果：`error_code=doc_rag_disabled`
- `Config.load("config.toml").doc_rag.enabled == False`
- `doc_rag.db` ready chunks = 11
- 代码修复：
  - `agent/tools/doc_rag.py`
  - `tests/test_doc_rag_tools.py`
  - `tests/test_doc_rag_citation_plugin.py`
  - `tests/test_doc_rag_toolset.py`
- 自动化回归：
  - `29 passed in 0.32s`
  - `76 passed in 0.50s`

影响：

- 后续测试必须先确认运行配置，否则 live smoke 会测到 disabled fallback，而不是 citation 能力。
- P10 e2e eval 应加入 disabled 场景，把“停止并提示启用”作为正确行为。

下一步：

- 关闭或保持 `doc_rag.enabled=false`，重跑 disabled live smoke，确认是否停止并提示启用。
- 启用本地 `[doc_rag]` 配置并重启 Agent，重跑 P9 CLI smoke。
- 如果 disabled live smoke 仍 fallback 到文件工具，再进入第二阶段设计执行器级阻断。

最新 disabled live smoke：

- `observe.db` turn id `346`
- 用户问题：`请从文档知识库中检索 agent runtime 负责什么？回答必须带文档引用`
- 工具链：`tool_search -> search_docs -> final`
- 结果：未再 fallback 到 `read_file/list_dir/shell`，第一阶段工具协议约束基本生效。
- 新发现：最终回复仍暗示“我可以先把 doc_rag 开启再查”，没有足够明确说明当前运行中的 Agent 需要重启后才能加载新配置。
- 结论：RAG-005 第一阶段解决了替代工具链问题，但需要补充 disabled 话术/协议字段，例如 `restart_required=true`、`can_self_enable=false` 或更明确的 `user_message`。
- 2026-07-11 第二小步已补充：
  - `restart_required=true`
  - `restart_target=agent_service`
  - `current_process_can_enable=false`
  - `retrieval_available_this_turn=false`
  - `config_key=doc_rag.enabled`
  - `required_config_value=true`
  - `user_message` 明确当前运行中的 Agent 不能继续检索，需修改配置并重启 Agent 服务。
  - 自动化回归通过，disabled live smoke 待复测。

关联文档：

- `my_md/governance/01-issue-index.md`
- `my_md/governance/02-current-issues.md`
- `my_md/governance/04-fix-roadmap.md`

### RAG-006: Document RAG 启用后 live smoke 暴露工具可见性和成本问题

场景：

- 完成 RAG-005 的配置启用后，重新执行 P9 live smoke。
- 用户提问：`请从文档知识库中检索agent runtime负责什么？回答必须带文档引用`。

发现：

- `search_docs` 已能成功进入检索链路，说明 Document RAG 索引、检索和 citation 字段可用。
- 最终回答包含真实 Document RAG citation：
  - `[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]`
  - `[my_md/doc_rag_corpus/manual_test.md > Agent Runtime > Tool Calling]`
- 但本轮 `react_iteration_count=7`，原因是 `search_docs` 和 `fetch_doc_chunk` 初始不可见，需要先失败或通过 `tool_search` 解锁。

处理：

- 将该问题登记为 `RAG-006`。
- 明确它不是检索质量问题，而是工具可见性和成本治理问题。
- 已调用审阅 skill 审阅计划。
- 修订后的方案不是把 `search_docs` 改成 always-on，而是在当前 turn 根据强文档意图做 turn-local preload。
- 修订后的方案要求强记忆/session 意图时临时压制 doc_rag LRU 残留，避免“上一轮查文档，下一轮问记忆”仍暴露 `search_docs`。
- 详细计划写入 `my_md/rag/19-document-rag-p10-intent-preload-plan.md`。

结果：

- Document RAG happy path 已经跑通，但路径效率不达标。
- 后续 P10 评估需要同时看“是否答对”和“是否以合理成本答对”。
- 计划审阅后已明确实现边界：不改 always-on，不写 LRU，只改当前 turn 的 effective visible tools。

证据：

- `observe.db` turn id `345`
- 工具链：`search_docs -> tool_search -> search_docs -> tool_search -> fetch_doc_chunk -> fetch_doc_chunk`
- `react_iteration_count=7`
- `react_input_sum_tokens=42008`

影响：

- 如果不治理工具可见性，真实用户每次文档问答都可能多跑 2-3 轮。
- 成本指标会影响后续对 RAG 版本优化的判断。

下一步：

- 实现 `agent/policies/doc_rag_intent.py`。
- 在 `DefaultReasoner.run_turn()` 接入 turn-local intent preload。
- 增加 unit intent 测试和 memory-after-doc-LRU 集成测试。
- 在 e2e eval 中加入 `max_react_iterations` 和 `max_tool_calls`。

关联文档：

- `my_md/governance/02-current-issues.md`
- `my_md/governance/04-fix-roadmap.md`
- `my_md/rag/19-document-rag-p10-intent-preload-plan.md`

### RAG-007: Document RAG citation 有效但证据支撑强度需要继续治理

场景：

- 同一轮 P9 live smoke 中，最终回答带有两个有效 citation。
- 用户指出可能存在“引用证据不匹配”的问题。

发现：

- 从来源校验看，两个 citation 均来自本轮 `search_docs` / `fetch_doc_chunk`，不是伪引用。
- 从语义忠实度看，“Agent runtime 负责管理 agent 的一次运行过程”有直接证据。
- “runtime 下辖 Tool Calling”更多来自 heading path `Agent Runtime > Tool Calling` 的结构推断，正文没有直接写明“下辖”。

处理：

- 将该问题登记为 `RAG-007`。
- 明确 citation validator 目前解决的是来源有效性，不等价于 claim/evidence 完全对齐。
- 后续要在回答约束和评估指标中区分“文档明确写了”和“从结构推断”。

结果：

- 当前 P9 citation 机制没有失败，但暴露出 P10 faithfulness 评估需求。
- 后续回答应避免把结构推断包装成文档明示事实。

证据：

- `fetch_doc_chunk` 返回：
  - `Agent runtime 负责管理 agent 的一次运行过程。`
  - `工具调用用于让 agent 访问外部能力。`
- 最终回答中的“下辖 Tool Calling”不是原文直接表述。

影响：

- 后续 judge 可能判为 evidence weak。
- 企业知识库问答中，即使 citation 真实，也需要防止模型对证据过度解释。

下一步：

- 在 Document RAG 回答约束中加入“直接证据/推断表达”的区分。
- 在 P10 eval 中增加 `claim_evidence_alignment`。
- 增加标题暗示但正文未明说的测试 case。

关联文档：

- `my_md/rag/12-document-rag-params-experiments.md`
- `my_md/rag/13-document-rag-evaluation.md`

## Local Agent

### LA-001: TaskPlan 边界治理后进一步暴露上下文召回授权问题

场景：

- TaskPlan 第一阶段完成工具注册、SQLite 状态、active task prompt 和 non-LRU 合同后，第二轮 CLI smoke 曾出现 15 轮 ReAct、spawn 误路由和“当前任务”语义混淆。
- 2026-07-14 实现 TaskPlan access/execution/completion 边界后，使用独立 CLI session 重跑四条真实 smoke。

发现：

- 创建、查看、更新 TaskPlan 与明确后台 job 的语义边界已经成立。
- turn `383/384/385` 分别稳定为 `inspect_task_plan -> final`、`update_task_step -> final`、`spawn_manage -> final`，均为 2 轮。
- turn `382` 成功阻止 spawn、Document RAG 和 local file 工具，但仍真实执行 `recall_memory`，并生成一次被 budget soft-stop 的 `search_messages`。
- 这说明问题已经从“TaskPlan 与后台执行混淆”收敛为“计划创建是否需要历史上下文”的能力授权问题。

处理：

- 已完成自动化边界模块：`task_plan_boundary.py`、`task_plan_completion.py`、中立 access/completion types，以及 prompt/tool description 约束。
- 已通过 final-only 保证三类 TaskPlan 工具成功后停止后续工具循环。
- 对新问题暂不直接全禁 memory；记录候选模型 `TaskPlanIntent.action + ContextRequirement + CapabilityScope + TurnBudget`。

结果：

- 计划创建从旧 smoke 的 15 轮降到 4 轮，累计 prompt token 从 `985779` 降到 `52205`。
- SQLite 中新任务有 3 个步骤，Step 1 更新为 `completed`，状态链路正确。
- 新问题边界明确：纯状态创建不应召回；只有显式偏好/历史依赖的计划才临时授权一次召回。

证据：

- observe turn `382-385`。
- `/home/jjh/.akashic/workspace/logs/agent.log` 16:31:04 - 16:32:25。
- `/home/jjh/.akashic/workspace/task_plans.db` 中任务 `task_87eb3d1b8d944efd9bf566a8ae7e7b30`。
- 自动化完整回归：`1481 passed, 3 warnings in 36.10s`。

影响：

- TaskPlan 已从工具可用性骨架演进为具备 access、execution、completion 边界的状态管理模块。
- 下一步不应继续追加零散工具名判断，而应把“上下文需求”提升为可复用策略维度。

下一步：

- 先形成 LA-001 的正式设计和测试矩阵。
- 验证纯计划、偏好计划、历史计划、查看、更新、后台 job 六类场景。
- 单独修正 final-only 日志 reason 的可观测性不一致。

关联文档：

- `my_md/local_agent/02-task-plan-first-phase-design.md`
- `my_md/governance/02-current-issues.md`
- `my_md/governance/04-fix-roadmap.md`
- `my_md/governance/05-design-decisions.md`

### LA-001 实施：从工具名边界演进到上下文 capability contract

场景：

- turn `382` 已证明 TaskPlan 可以阻止 spawn/RAG/local，但纯计划仍先调用 memory/session retrieval。
- 直接全禁 memory 会破坏“结合偏好”和“按照上次讨论”这两类合理需求。

发现：

- TaskPlan 动作和上下文需求必须分开建模；topic words 不能隐式授权历史召回。
- schema 可见、tool search 可发现、执行可授权、调用是否值得继续、action 是否完成是不同边界。
- 一次工具尝试的成本在返回失败或 hook 拒绝时已经发生，因此预算不能只统计成功结果。

处理：

- 引入 typed `TaskPlanTurnContract` 和 registry capability metadata。
- `TaskPlanAccessPolicy` 构建严格 allow scope；required provider 缺失时 fail closed，optional context provider 缺失时退化为 task state scope。
- `TaskPlanContextBudgetPolicy` 在 access gate 后执行一次性预算；召回后通过网关重新计算 visibility。
- `TaskPlanCompletionPolicy` 按 action 对应 capability、executor status 和 result success 判定 final-only。
- `DefaultReasoner` 只做窄接线，不修改 AgentLoop；严格 scope 同时关闭全局 deferred-tool hint。

结果：

- 纯计划自动化路径只暴露 create capability。
- 偏好/历史计划各最多一次对应召回，不能跨 family 或扩展到 `fetch_messages`。
- 同批重复、`ok:false`、denied/error、inspect-before-update 和 discovery-disabled 均有 E2E 回归。
- 最终完整 pytest：`1619 passed, 3 warnings in 38.10s`；独立审阅无剩余 Critical/Important。
- 隔离真实 smoke 验证 pure=2 轮、preference=3 轮、history=3 轮，inspect/update/background 均保持 2 轮。
- live smoke 发现并修复 no-create 动作否定的子串误匹配；进一步用 bounded regex 和明确优先级覆盖 plan/background 的 required、negated、positive 与 observe fallback，显式 update 仍优先。

影响：

- TaskPlan 的边界从工具名 blocklist 演进为可复用的 typed capability contract。
- runtime authorization 与 trace metadata 分离，降低模型输出或 trace 篡改改变权限的风险。
- LA-001 已完成自动化和真实模型验收；后续只把同批重复候选作为跨工具域的模型生成成本问题观察，不重新打开本次执行授权问题。
- 2026-07-15 主服务 turn `389-392` 再次验证 pure create、inspect、update、background observe 均为 2 轮且 `error=NULL`；主服务 SQLite 状态与工具链一致，基础复测 4/4 通过。
- Local Agent 的问题边界由“任务状态与上下文授权”推进到下一层“任务恢复与受控执行”。后续 `LA-002` 应引入 execution attempt 和幂等恢复，而不是把执行状态塞进 LRU 或 AgentLoop。

关联文档：

- `docs/superpowers/plans/2026-07-14-task-plan-context-capability-scope.md`
- `my_md/local_agent/02-task-plan-first-phase-design.md`
- `my_md/local_agent/03-task-plan-recovery-execution-design.md`
- `my_md/governance/06-star-log.md` CASE-004

### LA-002 实施：从 TaskPlan 状态骨架演进到可恢复受控执行

场景：

- LA-001 解决了计划 turn 的上下文授权，但 TaskPlan 仍没有独立 execution attempt、重复请求幂等和重启恢复。
- 直接让模型自由调用本地工具无法证明单步推进，也无法在进程中断时区分未执行、已执行和结果未知。

处理：

- 在 TaskPlan SQLite 事务边界内增加 attempt/event、request replay-first、owner/status/lease CAS 和 startup/session reconcile。
- 通过独立 `TaskExecutionTurnContract`、arbiter、Gateway/Boundary/Completion 和 RuntimeCoordinator 约束 claim/work/finish/defer/abort。
- 只允许 registry exact `read-only` 自动执行；write/external/unknown/shell 先持久化 waiting authorization，destructive 保持 core deny。
- turn-exit finalizer 对 provider error、cancel、timeout、max-iteration 和 missing finish 做确定终态收口。

结果：

- 自动化 full baseline `1835 passed, 3 warnings in 48.71s`；finalizer 注入集成 `10 passed`。
- 真实模型 replay 使用同 request ID 时只保留 attempt `attempt_366f8c1f90d1449b83b272a0cbab50de`，重复 turn 0 tools；新 request 同文本创建独立 Step 2 attempt。
- controlled restart 将 running attempt 变为 `runtime_restarted_outcome_unknown` blocked/pending，不自动重放；普通 continue 不新建，显式 retry 创建 attempt 2。
- 文件修改计划只进入 waiting authorization，目标未变且 write/edit/shell event 为 0；abort 后 step pending、历史保留。

影响：

- Local Agent 从“能保存计划状态”进入“能在安全边界内恢复并执行一个只读步骤”。
- 下一边界不再是 LA-002 recovery，而是 LA-003/P2 structured authorization request、批准/拒绝和 P3 diff/rollback。
- defer 专用 `requested_*` columns 尚未填充；provider replay final-only 还可能输出 literal tool syntax，均作为后续事实记录，不扩大本次完成声明。

关联文档：

- `my_md/local_agent/03-task-plan-recovery-execution-design.md` 第 31 节（持久化验收摘要）
- `my_md/governance/06-star-log.md` CASE-005

## System

### SYS-001: 建立集中式治理文档体系

场景：

- 整理 `my_md` 文档结构后，需要避免问题、演进、修复和 STAR 记录散落在各个业务目录。

发现：

- 全局 STAR 文档适合记录完整复盘案例，但不适合承载每个领域的过程流水。
- architecture、test、rag、system 这些代码完善方向都需要演进记录，但分散放置会增加查找成本。

处理：

- 新建 `my_md/governance/` 作为统一治理目录。
- 将 issue、current issues、domain evolution、fix roadmap、design decisions、STAR log 收敛到该目录。
- 学习、架构、测试、RAG、面试目录只保留领域知识和原始事实。

结果：

- 后续所有问题治理、演进、修复和复盘都从 `governance/` 入口查找。

证据：

- `my_md/README.md`
- `my_md/governance/README.md`
- `my_md/governance/06-star-log.md`

影响：

- 后续问题不会只散落在聊天或各业务目录里，可以统一治理，再按领域分类。

下一步：

- 每次修复、测试、设计变更后，优先判断是否需要更新 `03-domain-evolution.md`、`02-current-issues.md` 或 `06-star-log.md`。

关联文档：

- `my_md/governance/06-star-log.md`
