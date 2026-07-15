# Fix Roadmap

这个文档记录后续修复优先级和验证方式。

## 修复优先级

### 第零阶段：P9 Document RAG live smoke 配置与 disabled 行为

目标：

- 让 P9 真实 CLI/LLM smoke 能验证已实现的 citation 闭环。
- 避免 Document RAG 未启用时模型继续 fallback 到 `read_file` 形成无效工具链。

任务：

- 在本地测试配置中显式加入 `[doc_rag] enabled=true`，重启 Agent 后重新执行 P9 smoke。
- 确认 `search_docs` 在启用状态下返回 `ok=true`、`hit_count>0`、hits 带 `citation`。
- 确认最终回答包含 `[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]`。
- 已完成：disabled 场景增强，`search_docs` / `fetch_doc_chunk` 返回 `retryable=false`、`terminal=true`、`terminal_scope=document_rag`、`fallback_allowed=false`、`recommended_action=answer_doc_rag_disabled`。
- 已完成：工具描述补充 `doc_rag_disabled` 时直接告知用户启用配置，不要改用本地文件读取、`list_dir` 或 `shell` 替代 Document RAG 检索。
- 待执行：disabled live smoke，确认模型是否遵循工具协议停止 fallback。

验证：

- 启用场景：
  - `tool_search -> search_docs -> answer with citation`
  - 可选复杂问题：`tool_search -> search_docs -> fetch_doc_chunk -> answer with citation`
- 禁用场景：
  - `search_docs -> doc_rag_disabled -> final answer asks user to enable Document RAG`
  - 不应继续调用 `read_file`。
- 已通过自动化测试：
  - `tests/test_doc_rag_tools.py`
  - `tests/test_doc_rag_toolset.py`
  - `tests/test_doc_rag_citation_plugin.py`
  - `tests/test_citation_plugin.py`
  - `tests/test_plugin_manager.py`
- disabled live smoke 结果：
  - 已满足：不再调用 `read_file/list_dir/shell` 替代 Document RAG。
  - 待修正：最终回复必须明确“修改 `doc_rag.enabled=true` 后需要重启 Agent 服务”，不能暗示当前 Agent 可以直接启用并立即生效。
- 第二小步代码已完成：
  - disabled payload 已标记 `restart_required=true`、`restart_target=agent_service`、`current_process_can_enable=false`、`retrieval_available_this_turn=false`。
  - 工具返回和工具描述已明确：设置 `doc_rag.enabled=true` 后必须重启 Agent 服务。
  - 待执行：再次 disabled live smoke，确认最终回答包含“当前运行中的 Agent 无法继续检索 / 需要重启 Agent 服务”。

### 第零点五阶段：Document RAG 工具可见性、成本和 citation 忠实度

目标：

- 让 Document RAG happy path 不再因为工具未加载浪费 ReAct 轮次。
- 让 citation 不只“来源真实”，还要尽量做到“结论被证据直接支撑”。

任务：

- 已完成 P10a：新增强文档意图判断，强文档意图时只在当前 turn 预加载 `search_docs`。
- 已完成 P10a：强文档意图且命中原文/文档证据展开意图时，只在当前 turn 预加载 `fetch_doc_chunk`。
- 已完成 P10a：强记忆/session 意图且无强文档意图时，只在当前 turn 临时压制 `search_docs` / `fetch_doc_chunk` 的 LRU 残留。
- 已完成 P10a：不改 `doc_rag` toolset 的 always-on 策略，不向 `ToolDiscoveryState` 写入意图预加载结果。
- 已完成 P10a.1 自动化实现：强文档意图 turn 中，如果用户未显式要求源码/本地文件/仓库文件，通过 Tool Access Gateway 临时压制并执行前拦截 `shell`、`read_file`、`list_dir` 等本地文件工具，避免 Document RAG 跑偏。
- 已完成 P10a.1 自动化实现：强文档 + 原文/证据展开意图中，`search_docs` 与 `fetch_doc_chunk` 由同一个 current-turn access plan 暴露，`tool_search` 结果会在进入模型上下文前过滤被压制工具，不能重新解锁通用文件读取。
- 已完成 P10a.2 自动化实现：Turn Tool Boundary Manager 统一执行 access、budget、evidence-complete、ledger 和 trace，冗余 `tool_search/search_docs/fetch_doc_chunk` 会转为非执行型 `soft_stop`。
- 已完成 P10a.3 自动化实现：Boundary-Driven Early Finalization 在 `document_rag_evidence_complete` soft stop 后切换下一次 LLM 调用为 final-only，省略工具 schema，只允许基于已有 evidence 回答。
- 为文档问答增加早停策略：简单事实问题如果 `search_docs` snippet 已足够回答，不强制展开 chunk。
- 在工具描述或回答约束中加入：如果结论只是从标题层级推断，必须用“从章节结构看 / 可以理解为”等弱断言表达。
- 修复 CLI/IPC live smoke 稳定性：
  - 已完成：CLI 使用稳定 client/session id，不再用 `id(writer)` 作为唯一会话身份。
  - 已完成：outbound metadata 发给 CLI/TUI 前将 `tool_chain` 投影为 `tool_summary`，完整链路只保存在 observe/session。
  - 已完成：服务端发送前限制 payload 大小，超限时降级 metadata/content。
  - 已完成：CLI/TUI 服务端响应使用 `AKIP2` magic + length-prefixed frame，替代 newline-delimited JSON。
  - 已完成：运行日志落到 workspace 文件，便于追踪 IPC send/receive 异常。
- 在评估集中增加：
  - `max_react_iterations`
  - `max_tool_calls`
  - `expected_tools`
  - `forbidden_tools`
  - `citation_valid`
  - `evidence_alignment`

验证：

- P10a 自动化验证已通过：`43 passed in 0.48s`，覆盖纯策略、turn-local preload、memory-after-doc-LRU、Doc RAG toolset、tool visibility、reasoner 和 safety retry。
- 2026-07-11 14:26 live smoke 发现 P10a 后续缺口：强文档证据问题预加载已生效，但实际工具链为 `search_docs -> shell/read_file...`，共 15 次工具调用，`react_iteration_count=10`，`react_input_peak_tokens~=34858`；随后 CLI 提示 `Separator is found, but chunk is longer than limit` 并断连，第三轮未进入 observe。
- 2026-07-11 CLI IPC v2 自动化修复已完成：`AKIP2` frame、稳定 session id、`tool_summary` 投影、payload 治理和 workspace 文件日志均已覆盖测试；随后用户真实 CLI 重连测试确认默认继承之前 session。
- 2026-07-11 16:17 live smoke 复测：CLI IPC v2 未断连且 session 稳定，但强文档长证据 prompt 再次跑偏到 `read_file/shell`，turn `354` 工具链为 `read_file -> read_file -> shell -> search_docs -> shell -> shell -> read_file -> search_docs -> read_file`，`react_iteration_count=7`，`react_input_peak_tokens~=37978`。P10a.1 不能标记为未复现或跳过。
- 2026-07-11 16:32 用户真实 CLI 重连测试确认：默认 CLI 会继承之前 session，CLI-001 从 transport/session 角度关闭；下一步回到 RAG-006 P10a.1，治理强文档证据 turn 跑偏到 `shell/read_file/list_dir` 的问题。
- 2026-07-11 P10a.1 Tool Access Gateway 已完成自动化实现并通过回归：新增纯网关策略测试、reasoner 集成测试、P10a preload 合同迁移测试；`uv run --with pytest --with pytest-asyncio pytest tests/test_doc_rag_intent.py tests/test_doc_rag_intent_preload.py tests/test_agent_core_p2_reasoner.py tests/test_tool_search.py tests/test_tool_access_gateway.py tests/test_tool_access_gateway_reasoner.py -q` 为 `92 passed, 2 warnings`，运行时/通道 smoke 集合为 `81 passed`。随后已执行真实 CLI/LLM smoke。
- 2026-07-11 21:01 P10a.1 真实 CLI/LLM smoke 已通过关键目标：turn `361` 在强文档 + 原文 chunk 展开 prompt 下走 `tool_search -> search_docs -> fetch_doc_chunk -> fetch_doc_chunk -> fetch_doc_chunk -> search_docs -> fetch_doc_chunk`，未调用 `shell/read_file/list_dir`，`error=NULL`，CLI 未断连。gateway 日志显示本地文件工具已被 `visible_suppress` 和 `execution_block` 压制。
- 剩余成本问题：turn `361` 仍有一次多余 `tool_search` 确认可见工具，且重复检索/展开导致 `react_iteration_count=6`、`react_input_peak_tokens~=68857`；后续应进入“第五阶段：工具链成本控制”，而不是继续处理本地文件工具跑偏。
- 启用场景简单问题：
  - 预期链路：`search_docs -> final`
  - 目标 ReAct 轮次：2-3。
- 启用场景复杂问题：
  - 预期链路：`search_docs -> fetch_doc_chunk -> final`
  - 目标 ReAct 轮次：3-4。
  - 禁止链路：未显式要求源码时，不应调用 `shell/read_file/list_dir`。
- 记忆/session 场景：
  - fresh 记忆问题不应预加载 `search_docs`。
  - 同 session 上一轮调用过 `search_docs` 后，下一轮强记忆问题也不应因 LRU 残留暴露 `search_docs`。
- citation 忠实度：
  - 直接事实必须由 chunk 正文支撑。
  - 标题结构推断必须用弱断言表达。
  - 不应把“相关能力”写成“明确下辖”，除非正文直接支持。

### 第一阶段：降低测试噪声

目标：

- 让失败列表更接近真实系统问题。

任务：

- 修正 C/D 组过宽的 group-level 工具断言。
- 放宽中文同义表达断言。
- 修复 judge runner 的环境依赖问题。

验证：

- `python3 my_md/test_docs/eval_suite/deep_live_eval_runner.py --dry-run`
- 小范围 live case：A019、C011、C014、D015、D024。

### 第二阶段：记忆写入边界和污染清理

目标：

- 避免临时 session 信息进入长期记忆。
- 清理已经写入 memory2 的 `EVAL_SESSION_*` 临时测试污染数据。

候选方案：

- 提示词层：明确 `EVAL_SESSION_*`、`临时会话信息`、`不要写入长期记忆` 不得调用 `memorize`。
- 工具层：`memorize` 对明显临时/测试/session 标记做拒绝。
- 记忆抽取层：consolidation 继续保持高门槛，避免后台总结污染记忆。
- 数据清理层：对已有 active memory 中的 `EVAL_SESSION_*` 做清理或标记失效。

验证：

- DL-A001
- DL-B001
- DL-B-010 到 DL-B-023 中的隔离用例
- 检查 memory2 中不出现 `EVAL_SESSION_*`。
- 重点验证 `DL-B-012`：memory2 不再注入 `EVAL_SESSION_B012 的 A 变量是 value-a-012`。

### 第三阶段：消息回源和搜索的 session 边界

目标：

- 避免当前 session 通过 `fetch_messages` 或 `search_messages` 读取其他 session 的原始消息。

候选方案：

- 在工具上下文中注入完整 `session_key`。
- `fetch_messages` 默认只允许读取当前 session 的消息。
- `search_messages` 默认限定当前 session。
- 如果需要跨 session 回源长期记忆证据，设计显式授权参数或独立工具路径。

验证：

- DL-B-012
- DL-B-023
- 新增单元测试：当前 session fetch 其他 session source_ref 应被拒绝或返回空。
- 新增单元测试：不显式传全局搜索时，`search_messages` 不返回其他 session 消息。

### 第四阶段：工具禁用硬约束

目标：

- 用户明确说“不用工具/不要调用工具”时，系统能硬性禁用工具。

候选方案：

- 在 turn 开始前识别本轮 no-tool 约束。
- 将可见工具集合置空，或只保留必要的安全/元工具。
- 在 observe 中记录本轮工具禁用原因。

验证：

- DL-A-014
- DL-A-019
- DL-A-028
- DL-F-013

### 第五阶段：工具链成本控制

目标：

- 简单问题减少不必要工具调用。
- P10a.2 将 Document RAG 从“工具可用性正确”推进到“工具链成本可控”：强文档证据请求不再转向本地文件工具后，继续减少多余 `tool_search`、重复 `search_docs` 和重复 `fetch_doc_chunk`。
- 设计入口：`my_md/rag/20-document-rag-p10a2-tool-boundary-design.md`。
- 设计已完成审阅并修订：`soft_stop` 明确为不执行目标工具的非致命边界结果；决策合并优先级明确 core access block 高于 budget/evidence/plugin；ledger 和负向测试要求已补齐。
- 自动化实现已完成：`TurnToolBoundaryManager` 已接入 `DefaultReasoner`，targeted suite `100 passed, 2 warnings`，full pytest `1361 passed, 3 warnings`。
- 2026-07-12 真实 CLI/LLM smoke 已执行：P10a.2 成功把真实工具执行收敛到 `search_docs + fetch_doc_chunk`，并把冗余 `tool_search`、额外 `fetch_doc_chunk`、额外 `search_docs` 转为 `tool_boundary_soft_stop`；但仍消耗 5 轮 LLM、`react_input_peak_tokens~=73267`、`prompt_tokens=419680`，说明剩余瓶颈已从“工具执行成本”转为“soft stop 后的 LLM 轮次/token 成本”。
- 2026-07-12 P10a.3 自动化实现已完成：`TurnCompletionController` 消费 P10a.2 的 `document_rag_evidence_complete` soft stop；`DefaultReasoner` 下一轮使用 `tools=[]`，并通过 `context_retry.turn_completion` 暴露 `action/reason/metadata`。验证：targeted suite `24 passed`，broader relevant suite `55 passed`，full pytest `1373 passed, 3 warnings`，compileall exited 0。随后已执行真实 CLI/LLM smoke。
- 2026-07-12 P10a.3 真实 CLI/LLM smoke 已执行：turn `364` 出现预期 `[tool_boundary] soft_stop ... document_rag_evidence_complete` 与 `[turn_completion] final_only ...` 日志；真实成功执行工具为 `search_docs + fetch_doc_chunk`，未调用 `shell/read_file/list_dir`，`react_iteration_count=3`，`prompt_tokens=265562`，对比 turn `362` 的 5 轮/`419680` prompt tokens 明显下降。
- P10a.3 后续剩余问题：final-only 回答忠实度。turn `364` 最终回答把两个被 soft stop 的候选 chunk 写成“原文 chunk 展开”，但这些 chunk 没有真实 `fetch_doc_chunk` 成功结果；后续应让 final-only 阶段区分 fetched chunk 原文和 `search_docs` hit/snippet 摘要。
- 2026-07-13 P10a.4a Evidence Contract 已完成：新增证据合同模块，将证据分成 `fetched_text`、`retrieval_snippet`、`soft_stopped_candidate`，final-only 前注入回答约束，保证只有真实成功 `fetch_doc_chunk` 的内容才能被称为“原文展开”。自动化验证：相关 suite `27 passed`，full pytest `1376 passed, 3 warnings`，compileall 和 `git diff --check` 通过。
- 2026-07-13 P10a.4a 最新真实 CLI/LLM smoke 已验证：turn `365/366` 均未调用 `shell/read_file/list_dir`，均只真实成功执行 `search_docs + fetch_doc_chunk`，final answer 已正确把未真实 fetch 的后续证据称为“检索命中/检索摘要”，不再夸大为原文展开。
- 2026-07-13 P10a.4b Bounded ReAct / Batch Boundary 自动化实现已完成：新增 `ReactBoundaryManager`，在真实工具结果入账后触发 proactive final-only recommendation，并在同一 assistant tool-call batch 中把预算外 Document RAG 调用标记为 `batch_skipped_by_react_boundary`。同批次 skipped calls 仍追加合法 tool result，但不计入成功 `tools_used`，不写入 evidence ledger，不再表现为普通 `tool_boundary_soft_stop`。验证：targeted P10a suite `48 passed`，full pytest `1391 passed, 3 warnings`，compileall 通过。随后已执行真实 CLI/LLM smoke。
- 2026-07-13 P10a.4b 真实 CLI/LLM smoke 已执行：
  - turn `367` 简单文档问题：`search_docs -> final`，`react_iteration_count=2`，`[react_boundary] final_only reason=document_rag_retrieval_complete`。
  - turn `368` 原文证据问题：`search_docs -> fetch_doc_chunk -> final`，`react_iteration_count=3`，同批次额外两个 `fetch_doc_chunk` 被 `react_boundary_batch_skip` 跳过。
  - turn `369` 文档 + 源码问题：`read_file x3 -> final`，显式源码读取未被 RAG final-only 截断；但没有当前 turn fresh RAG。
  - turn `370` 历史工具查询：`search_messages -> final`，未被 `search_docs/fetch_doc_chunk` LRU 残留污染。
  - 新问题：turn `370` 对 turn `369` 的工具使用自报不准确，说明 session/meta 的“用了哪些工具”应改走结构化 observe/session tool trace，而不是让模型从自然语言上下文推断。

候选方案：

- 对已在 current-turn schema 中可见的工具，减少 `tool_search(select:search_docs,fetch_doc_chunk)` 确认轮次；必要时在工具访问计划或 reasoner 提示中暴露“目标工具已可用”的事实。
- 增加 turn-local Document RAG 工具预算：简单文档问题通常最多 1 次 `search_docs`；强文档 + 原文/证据展开通常最多 1 次 `search_docs` 和 1-2 次 `fetch_doc_chunk`。
- 增加 evidence-complete 早停提示：当已取得可引用 chunk 且能回答用户问题时，优先生成最终回答，不继续展开相邻 chunk。
- 对连续同类工具调用增加 loop guard 或成本提示，重点覆盖重复 `search_docs`、重复 `fetch_doc_chunk` 和工具已可见后的 `tool_search`。
- 保持第一版 soft governance：重复/超预算时优先 `soft_stop`，不执行目标工具但给模型结构化提示；本地文件工具误用仍由 access policy hard block。
- P10a.3 已实现第一版 Boundary-Driven Early Finalization：当前仅对 `doc_qa_with_evidence` + `document_rag_evidence_complete` 启用 final-only；no-hit、无 citation chunk、显式源码/本地文件请求不会触发。
- P10a.4a 已实现 Evidence Contract：final-only 阶段区分 fetched original text、retrieval snippets 和 soft-stopped candidates，防止回答证据标签失真。
- P10a.4b 已实现受控 ReAct 边界：工具结果入账后由 Evidence Contract 判断证据是否足够，再交给 Turn Completion 产出 final-only；React Boundary 只提供 `recommend_final_only` 和 same-batch skip。必要时后续再评估 provider 层 `parallel_tool_calls=false`，但当前第一版不依赖 provider 特性。
- P10a.4b 后续不再优先处理 Document RAG 长工具链：真实 smoke 已证明主路径收敛。下一步优先设计结构化 turn/tool trace 查询能力，让 session/meta 问题能够准确回答“上一轮/第 N 个问题用了哪些工具”，并明确“项目文档 + 源码”场景是否必须 fresh RAG。
- 2026-07-13 已完成结构化 Turn Trace Query 实现计划并审阅到可执行状态：
  - 计划文档：`docs/superpowers/plans/2026-07-13-turn-trace-query.md`。
  - 推荐实现顺序：core trace query service -> observe slim trace 元数据保真与非 LRU 合同 -> `inspect_turn_trace` 工具适配器 -> ToolAccessGateway 可见性与 protected `_session_key` 上下文 -> turn `370` 风格 E2E 回归。
  - 验收重点：工具历史问题必须通过当前 session 的 `observe.turns.tool_chain_json` / `tool_calls` 回源；被 boundary block/soft-stop/batch-skip 的调用不能算真实执行；混合 doc+tool-history prompt 不能重新暴露 stale `search_docs/fetch_doc_chunk`。
- 2026-07-13 结构化 Turn Trace Query 已完成自动化实现：
  - 已落地 core service、deferred `inspect_turn_trace`、observe slim metadata preservation、protected `_session_key` 绑定和非 LRU 合同。
  - 已新增 turn `370` 风格 E2E 回归：真实 `InspectTurnTraceTool` 读取临时 observe DB，第二个问题真实工具链为 `read_file x3` 时，最终回答不再从上下文误报 Document RAG 工具。
- 2026-07-14 结构化 Turn Trace Query 真实 CLI/LLM smoke 已通过：
  - turn `371`：简单文档引用链路为 `search_docs -> final`，`react_iteration_count=2`。
  - turn `372`：原文证据链路为真实 `search_docs + fetch_doc_chunk`，同批次后续 3 个 `fetch_doc_chunk` 被 `react_boundary_batch_skip` 跳过，`react_iteration_count=3`。
  - turn `373`：文档 + 源码请求真实执行 `read_file x2 + search_docs + fetch_doc_chunk`，`react_iteration_count=5`；显式源码读取和 fresh RAG 均被允许。
  - turn `374`：工具历史查询链路为 `inspect_turn_trace -> final`，`react_iteration_count=2`，没有调用 `search_messages`、`search_docs/fetch_doc_chunk`；回答以 observe trace 为准，正确报告 turn `373` 的工具链。
  - 结论：turn `370` 的 trace-source-of-truth 问题已通过真实 CLI smoke 验证修复。下一步不再优先处理工具历史正确性，而是评估两个优化项：减少 same-batch 冗余 tool-call 生成，以及明确“项目文档 + 源码”是否总是要求当前 turn fresh RAG。
- 2026-07-14 已明确混合问题产品规则：`项目文档 + 源码` 默认必须在当前 turn 重新 RAG。turn `373` 的 fresh `search_docs/fetch_doc_chunk` 不再作为语义问题处理，只保留为成本优化观察项。
- 2026-07-14 same-batch 冗余 `fetch_doc_chunk` 暂不进入立即实现：当前接受其根因是模型在同一 assistant message 中基于多个 `search_docs` 候选并行规划多个证据展开，而 boundary 只能拦截执行、不能阻止已生成的 tool-call token。后续若继续优化，路线按优先级为：
  - 先评估 provider 是否支持对 Document RAG turn 设置 `parallel_tool_calls=false` 或等价单工具调用限制。
  - 再收紧 `search_docs/fetch_doc_chunk` schema 和 context hint：默认只展开最相关一个 chunk，除非用户要求多章节/多条证据。
  - 再考虑让 `search_docs` 返回 `recommended_next_chunk_id` / `fetch_budget=1`，把下一步展开建议前移到检索层。
  - 最后才考虑固定编排式 Document RAG workflow，避免过早限制开放式 ReAct 能力。
- 增强普通日志：`soft_stop` 应以 `[tool_boundary] soft_stop tool=... reason=...` 形式进入 agent log，避免只能通过 observe DB 判断拦截是否发生。
- 增强普通日志已覆盖自动化：`[tool_boundary] soft_stop ...` 和 `[turn_completion] final_only ...` 均有测试断言。
- 在 observe/e2e eval 中落地成本指标：`max_react_iterations`、`max_tool_calls`、`max_doc_rag_search_calls`、`max_doc_chunk_fetch_calls`。

验证：

- DL-H001
- DL-H-010 到 DL-H-014
- DL-H-013 特别关注工具调用次数。
- P10a.2 简单文档事实：预期 `search_docs -> final`，目标 2-3 轮。
- P10a.2 强文档证据展开：预期 `search_docs -> fetch_doc_chunk -> final`，目标 3-4 轮，通常不超过 4 次工具调用。
- 回归 turn `361` 同类 prompt：不调用 `shell/read_file/list_dir` 的 P10a.1 结论保持不变，同时工具链从 6 轮/7 次工具调用下降。
- 负向回归：no-hit、无 citation chunk、显式 broader exploration 不应被过早 evidence-complete；插件规则不能绕过 disabled/no-tool/core access block。
- P10a.2 自动化和真实 smoke 均已验证“目标工具不会重复执行”；P10a.3 自动化和真实 smoke 已验证 evidence-complete 后的下一轮 final-only，真实 ReAct 轮次已降到 3；P10a.4a 自动化和真实 smoke 已验证 final-only 证据标签不再夸大；P10a.4b 自动化和真实 smoke 已验证 same-batch 多余 `fetch_doc_chunk` 会被 batch boundary skip，且 happy path 收敛为 `search_docs -> fetch_doc_chunk -> final`。
- session/meta 工具历史查询已在 turn `374` 真实 CLI smoke 中验证：应使用 `inspect_turn_trace -> final`，不再依赖 `search_messages` 或自然语言上下文推断。

### 第六阶段：TaskPlan 上下文召回授权与成本控制

状态：自动化、独立代码审阅和隔离真实 CLI/LLM smoke 均已完成，问题编号 `LA-001`。

计划文档：`docs/superpowers/plans/2026-07-14-task-plan-context-capability-scope.md`。

目标：

- 纯计划状态创建默认不调用 memory/message retrieval，收敛为 `create_task_plan -> final`。
- 保留“结合我的偏好/记忆”和“按照上次讨论”这两类合理召回能力。
- 不把 memory 工具全局禁用，也不继续在 TaskPlan policy 中堆叠零散工具名特判。

当前证据：

- turn `382`：`recall_memory -> search_messages(soft-stop) -> create_task_plan -> final`，4 轮，累计 `prompt_tokens=52205`。
- turn `383`：`inspect_task_plan -> final`，2 轮。
- turn `384`：`update_task_step -> final`，2 轮。
- turn `385`：`spawn_manage -> final`，2 轮。
- 对比旧 smoke 的 15 轮/`985779` prompt tokens，主问题已解决，剩余成本集中在上下文召回。

已完成实现顺序：

1. 在 `TaskPlanIntent` 中增加 `context_requirement = none | long_term_memory | session_history`。
2. 定义 capability scope，将 `task_state_read/write`、`memory_retrieval`、`session_history` 映射到已注册工具。
3. plan-create/none 使用严格 turn-local allow scope；显式 memory/history 意图只临时增加对应 capability。
4. 对上下文召回设 turn budget：最多一次，召回后只能进入 create/final/clarification。
5. completion 继续复用 `TaskPlanCompletionPolicy`，不修改 AgentLoop 主循环，不写 ToolDiscoveryState/LRU。
6. 修正 final-only 普通日志，让日志 reason 与最终 `TurnCompletionDecision.reason` 一致。

自动化结果：

- capability metadata、严格 scope、one-shot budget、动态 schema 退场和 action-aware completion 均已接入。
- discovery disabled 的普通 turn 保持原有全工具行为，严格 TaskPlan turn 仍受合同约束。
- 同批重复召回、`ok:false`、hook denied/error、跨 context family、inspect-before-update 和 completion denied/error 均有 reasoner 回归。
- 严格 scope 已关闭全局 deferred-tool 提示，避免 schema 与 prompt 授权矛盾。
- 最终完整 pytest：`1619 passed, 3 warnings in 38.10s`；独立审阅无剩余 Critical/Important。
- 真实 pure/preference/history/inspect/update/background smoke 均通过；纯计划从 turn `382` 的 4 轮收敛到 2 轮，偏好/历史各只有一次真实上下文召回。
- live smoke 发现并修复 no-create 动作否定误匹配，避免“不创建计划”错误激活 strict create scope。

验证矩阵：

- 纯计划：`create_task_plan -> final`，2 轮，memory/message/spawn/RAG/local 均为 0。
- 偏好计划：`recall_memory <= 1 -> create_task_plan -> final`。
- 历史计划：`search_messages <= 1 -> create_task_plan -> final`，默认限定当前 session。
- 召回无结果：不升级到更多检索工具；创建计划或询问必要澄清。
- inspect/update/background-job：保持 turn `383-385` 已验证行为。
- 完整回归保持 Document RAG、Turn Trace、memory-after-doc-LRU 和 CLI session 行为不变。

2026-07-15 主服务复测：

- turn `389-392` 分别为 `create_task_plan`、`inspect_task_plan`、`update_task_step`、`spawn_manage` 后 final，全部 2 轮且 `error=NULL`。
- 纯计划首轮只暴露 create provider；四轮没有 LRU 预加载污染，TaskPlan SQLite 第一步更新结果正确。
- 基础 4/4 再次通过；偏好/历史/否定路径沿用 2026-07-14 隔离 live gate 和自动化证据，不因未在同一天重复运行而改变 LA-001 fixed 状态。

`LA-002` 第一版已完成：active task/attempt 重启恢复、stale step 判定、request-ID 幂等、受控只读单步推进、显式 retry/abort 和待授权状态均通过自动化与隔离真实模型 smoke。

设计文档：`my_md/local_agent/03-task-plan-recovery-execution-design.md`。`LA-002a Recovery Foundation` 与 `LA-002b Controlled Read-only Execution` 已交付；第一版只自动允许 registry `read-only` 工具，其他风险进入 waiting authorization。

Task 10 最终复审结果：focused `189 passed`，compatibility `278 passed`，full `1838 passed, 3 warnings`；真实 replay/restart/defer/abort 通过，write/edit/shell 真实事件为 0；failed retry 与 ordinary continue 的竞争已改为 Store 原子 claim。下一阶段 `LA-003/P2` 先规范化 structured authorization request 和批准/拒绝协议，再由 P3 diff/snapshot/rollback 决定是否开放文件写入。

## 暂不处理

- 大规模重构 AgentLoop。
- 重新设计 memory2 数据结构。
- 新增完整 Agent Gateway。

这些内容可以作为后续演进，但不应阻塞当前失败修复。
