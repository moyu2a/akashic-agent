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
