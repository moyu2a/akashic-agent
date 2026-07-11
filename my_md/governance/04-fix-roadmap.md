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

- 新增强文档意图判断，强文档意图时只在当前 turn 预加载 `search_docs`。
- 强文档意图且命中原文/文档证据展开意图时，只在当前 turn 预加载 `fetch_doc_chunk`。
- 强记忆/session 意图且无强文档意图时，只在当前 turn 临时压制 `search_docs` / `fetch_doc_chunk` 的 LRU 残留。
- 不改 `doc_rag` toolset 的 always-on 策略，不向 `ToolDiscoveryState` 写入意图预加载结果。
- 为文档问答增加早停策略：简单事实问题如果 `search_docs` snippet 已足够回答，不强制展开 chunk。
- 在工具描述或回答约束中加入：如果结论只是从标题层级推断，必须用“从章节结构看 / 可以理解为”等弱断言表达。
- 在评估集中增加：
  - `max_react_iterations`
  - `max_tool_calls`
  - `expected_tools`
  - `forbidden_tools`
  - `citation_valid`
  - `evidence_alignment`

验证：

- 启用场景简单问题：
  - 预期链路：`search_docs -> final`
  - 目标 ReAct 轮次：2-3。
- 启用场景复杂问题：
  - 预期链路：`search_docs -> fetch_doc_chunk -> final`
  - 目标 ReAct 轮次：3-4。
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

候选方案：

- 简单任务工具预算。
- 已获得足够证据后的早停提示。
- 对连续同类工具调用增加 loop guard 或成本提示。

验证：

- DL-H001
- DL-H-010 到 DL-H-014
- DL-H-013 特别关注工具调用次数。

## 暂不处理

- 大规模重构 AgentLoop。
- 重新设计 memory2 数据结构。
- 新增完整 Agent Gateway。

这些内容可以作为后续演进，但不应阻塞当前失败修复。
