# Document RAG P10 Intent Preload Plan

## 目标

减少 Document RAG 明确文档问题中的工具发现轮次，让强文档意图问题不再先经过 `tool_search` 才能看到 `search_docs`。

目标链路：

```text
disabled 文档问题：search_docs -> final
enabled 简单文档问题：search_docs -> final
enabled 原文证据问题：search_docs -> fetch_doc_chunk -> final
```

同时避免把长期记忆、聊天记录、session 问题误触发到 Document RAG。

## 执行状态

2026-07-11 P10a 代码实现已完成：

- 新增 `agent/policies/doc_rag_intent.py`，实现纯规则 `decide_doc_rag_preload(text)`。
- `DefaultReasoner.run_turn()` 已接入 turn-local `effective_preloaded`：
  - 强文档意图当前 turn 预加载 `search_docs`。
  - 强文档意图 + 原文/证据展开意图当前 turn 预加载 `fetch_doc_chunk`。
  - 强记忆/session 意图且无强文档意图时，当前 turn 临时压制 `search_docs` / `fetch_doc_chunk` 的 LRU 残留。
- 未修改 `doc_rag` toolset 的 always-on 策略。
- 未将意图预加载写入 `ToolDiscoveryState` / LRU；只有实际工具调用仍按既有逻辑进入 LRU。
- 已新增 `tests/test_doc_rag_intent.py` 和 `tests/test_doc_rag_intent_preload.py`，覆盖纯策略和 memory-after-doc-LRU 场景。

自动化验证：

```text
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_doc_rag_intent.py \
  tests/test_doc_rag_intent_preload.py \
  tests/test_doc_rag_toolset.py \
  tests/test_loop_tool_visibility.py \
  tests/test_agent_core_p2_reasoner.py \
  tests/test_safety_retry_service.py -q

43 passed in 0.48s
```

仍需后续真实 CLI/LLM smoke 或 P10b e2e eval 验证：

- 简单文档问题是否实际收敛到 `search_docs -> final`。
- 原文证据问题是否实际收敛到 `search_docs -> fetch_doc_chunk -> final`。
- 同 session 上一轮文档检索后，下一轮强记忆/session 问题是否不再暴露 Document RAG 工具。

2026-07-11 14:26 live smoke 新发现：

- P10a 预加载生效：第二轮日志显示 `search_docs=yes fetch_doc_chunk=yes suppress=no reason=strong_doc_with_fetch_intent`。
- 但原文证据问题没有收敛到目标链路，实际工具链为：

  ```text
  search_docs -> shell -> read_file -> read_file ... -> final
  ```

- observe turn `349`：
  - `react_iteration_count=10`
  - `react_input_peak_tokens~=34858`
  - 工具调用 15 次
  - `error=NULL`
- 第二轮主链完成后，IPC 日志出现 `[cli] client disconnected session=cli:cli-140554156611568`；第三轮未进入 `observe.turns`。
- CLI 界面同时提示 `Separator is found, but chunk is longer than limit`。该提示来自 Python `asyncio.StreamReader.readline()` 的单行读取限制，说明 IPC 返回的一整行 JSON payload 过大。
- 结论：P10a 解决的是 Document RAG 工具可见性，但还没有治理强文档 turn 的非 RAG 工具空间。强文档证据问题仍可能被模型解释成“查项目源码/仓库文件”，转向 `shell/read_file`，并放大 CLI/TUI outbound metadata。

新增后续小步 P10a.1：

- 强文档意图 turn 中，如果用户未显式要求源码/本地文件/仓库文件，当前 turn 临时压制或强约束 `shell`、`read_file`、`list_dir` 等本地文件工具。
- 强文档 + 原文/证据展开意图中，`fetch_doc_chunk` 是 `search_docs` 命中后的优先展开路径。
- e2e eval 增加 forbidden tools：强文档证据 case 默认禁止 `shell/read_file/list_dir`。
- CLI/IPC 同步治理：
  - 已完成 CLI IPC v2：CLI 使用稳定 session id，不用 `id(writer)` 绑定会话。
  - 已完成 CLI IPC v2：发给 CLI/TUI 的 metadata 将 `tool_chain` 投影为 `tool_summary`，完整链路保留在 observe/session。
  - 已完成 CLI IPC v2：服务端发送前限制 outbound payload 大小，超限时降级 metadata/content。
  - 已完成 CLI IPC v2：服务端响应使用 `AKIP2` magic + length-prefixed frame，替代 newline-delimited JSON。
  - 已完成 CLI IPC v2：运行日志落到 workspace 文件，便于复盘断连原因。

2026-07-11 更新：

- CLI-001 已由 CLI IPC v2 transport 修复，自动化回归覆盖大 payload、稳定 session 重连、CLI/TUI framed receive 和 workspace logging。
- 剩余 P10a.1 问题仍是 Document RAG 工具治理：强文档证据请求可能跑偏到 `shell/read_file/list_dir`，需要单独约束非 RAG 工具空间。
- 2026-07-11 16:17 复测没有复现 CLI 断连，但复现了 P10a.1 工具链跑偏：turn `354` 对强文档长证据 prompt 调用了 `read_file/read_file/shell/search_docs/shell/shell/read_file/search_docs/read_file`，`react_iteration_count=7`，`react_input_peak_tokens~=37978`。因此不能将 P10a.1 记为“未复现并跳过”；本轮仅记录，后续回到工具治理时继续处理。
- 2026-07-11 16:25 最新检查确认：当前没有更新的 observe turn 能覆盖 turn `354` 的结论。按本轮决策暂不继续实现 P10a.1 修复，但文档状态保持“已复现/open”，以后出现同类现象时从这里继续。
- 2026-07-11 16:32 用户真实 CLI 测试确认：默认重启 CLI 会继承之前 session。CLI-001 的稳定 session 路径已完成真实界面验证；P10a/P10a.1 后续不再把 CLI session 断连作为主阻塞项。
- 2026-07-11 P10a.1 Tool Access Gateway 已完成自动化实现：`agent/policies/tool_access.py` 统一输出 current-turn `visible_add`、`visible_suppress`、`tool_search_block`、`execution_block`；`DefaultReasoner` 接入初始 schema 可见性、`tool_search` 结果过滤与解锁合并、执行前 gate、工具结果观察。强文档证据请求未显式要求源码/本地文件时会压制并阻断 `shell/read_file/list_dir`；显式源码/路径请求仍放行。真实 CLI/LLM smoke 待执行。
- 2026-07-11 21:01 真实 CLI/LLM smoke 已验证 P10a.1 关键目标：turn `361` 对强文档 + 原文 chunk 展开 prompt 走 `tool_search -> search_docs -> fetch_doc_chunk -> fetch_doc_chunk -> fetch_doc_chunk -> search_docs -> fetch_doc_chunk`，未调用 `shell/read_file/list_dir`，`error=NULL`，CLI 未断连。该结果证明 Tool Access Gateway 已阻断本地文件工具跑偏。剩余问题转为成本治理：仍存在多余 `tool_search` 确认和重复 `search_docs/fetch_doc_chunk`，`react_iteration_count=6`，`react_input_peak_tokens~=68857`。
- P10a.2 已登记为下一步：治理 Document RAG 工具链成本，不再把本地文件工具跑偏作为当前主问题。目标是减少已可见工具下的 `tool_search` 确认，限制重复 `search_docs/fetch_doc_chunk`，并在 evidence complete 时早停；强文档证据场景目标收敛到约 3-4 轮、通常不超过 4 次工具调用。正式设计见 `my_md/rag/20-document-rag-p10a2-tool-boundary-design.md`。
- 2026-07-12 P10a.2 设计已审阅并修订：`soft_stop` 明确为不执行目标工具的非致命边界结果；决策合并优先级明确 disabled/no-tool/core access block 不能被 budget/evidence/plugin 放宽；ledger 字段和负向测试要求已补齐。

## 审阅结论

已调用方案审阅。审阅结论：

- 不建议改 `always_on`，否则所有 turn 都会暴露 Document RAG 工具。
- 不建议把意图预加载写入 `ToolDiscoveryState` / LRU，否则“上一轮查文档，下一轮问记忆”会被污染。
- 应实现 **turn-local intent preload**：只在当前 turn 临时合并到 visible tools。
- 需要处理 LRU 残留：如果当前问题是强记忆/session 意图且没有强文档意图，应在本 turn 临时压掉 `search_docs` / `fetch_doc_chunk` 的 LRU 预加载。
- 规则应保守：宁可漏预加载，让模型走 `tool_search`，也不要把非文档问题误导到 Document RAG。

## 设计边界

不做：

- 不改 `doc_rag` toolset 的 always-on 策略。
- 不把 `search_docs` 永久加入 always-on。
- 不改 `ToolDiscoveryState` 的 LRU 写入规则。
- 不强制模型调用工具，只改变当前 turn 的工具可见性。
- 不引入 LLM intent classifier。

要做：

- 新增纯规则意图判断。
- 在当前 turn 中临时预加载 Document RAG 工具。
- 对强记忆/session 意图做当前 turn 的 doc_rag LRU suppression。
- 记录预加载原因，方便 observe/日志排查。

## 文件计划

新增：

- `agent/policies/doc_rag_intent.py`
  - 放置 Document RAG 工具可见性意图策略。
  - 不放在 `agent/tools/`，因为它不是工具实现，而是路由/可见性策略。

新增测试：

- `tests/test_doc_rag_intent.py`
  - 测纯函数意图判断。

修改：

- `agent/core/passive_turn.py`
  - 在 `DefaultReasoner.run_turn()` 中，取出 LRU preloaded 后、渲染 prompt 前，计算 turn-local Document RAG preload。
  - 将 `effective_preloaded = lru_preloaded | intent_preloaded - intent_suppressed` 只传给当前 turn。
  - 不写回 `ToolDiscoveryState`。

可能修改：

- `agent/core/runtime_support.py`
  - 仅当需要结构化记录 preload 决策时调整数据结构。

测试可能涉及：

- `tests/test_doc_rag_toolset.py`
- 现有 passive turn / reasoner 相关测试。

## 意图判断接口

建议：

```python
from dataclasses import dataclass
from typing import Literal

DocRagIntentConfidence = Literal["none", "low", "high"]

@dataclass(frozen=True)
class DocRagPreloadDecision:
    preload_search_docs: bool
    preload_fetch_doc_chunk: bool
    suppress_doc_rag_lru: bool
    confidence: DocRagIntentConfidence
    reason: str
    matched_terms: tuple[str, ...] = ()
```

函数：

```python
def decide_doc_rag_preload(text: str) -> DocRagPreloadDecision:
    ...
```

`reason` 使用稳定 code，例如：

```text
strong_doc_intent
strong_doc_with_fetch_intent
blocked_by_explicit_no_doc
blocked_by_memory_intent
no_doc_intent
```

不要用长自然语言作为测试断言。

## 规则优先级

优先级从高到低：

1. 显式禁止文档：
   - `不要查文档`
   - `不要用文档`
   - `只从长期记忆`
   - `只从记忆`

   结果：

   ```text
   preload_search_docs = false
   preload_fetch_doc_chunk = false
   suppress_doc_rag_lru = true
   reason = blocked_by_explicit_no_doc
   ```

2. 显式强文档：
   - `文档知识库`
   - `Document RAG`
   - `doc rag`
   - `文档检索`
   - `检索文档`
   - `从文档中检索`
   - `从知识库中检索`
   - `知识库里检索`
   - `根据文档回答`
   - `回答必须带文档引用`
   - `文档引用`
   - `引用文档来源`
   - `项目文档`
   - `文档库`
   - `资料库`
   - `按资料回答`
   - `search_docs`
   - `fetch_doc_chunk`

   结果：

   ```text
   preload_search_docs = true
   suppress_doc_rag_lru = false
   reason = strong_doc_intent
   ```

3. 强文档 + 展开证据意图：
   - 只有在已命中强文档意图时，以下词才触发 `fetch_doc_chunk`：
     - `原文`
     - `完整内容`
     - `文档证据`
     - `展开`
     - `chunk`
     - `片段`
     - `引用来源`
   - 显式 `fetch_doc_chunk` 也触发。

   结果：

   ```text
   preload_search_docs = true
   preload_fetch_doc_chunk = true
   reason = strong_doc_with_fetch_intent
   ```

4. 强记忆/session 且无强文档：
   - `长期记忆`
   - `记忆`
   - `我之前`
   - `你还记得`
   - `聊天记录`
   - `session`
   - `会话`
   - `刚才说`
   - `历史消息`
   - `我的偏好`
   - `从长期记忆`
   - `回看消息`

   结果：

   ```text
   preload_search_docs = false
   preload_fetch_doc_chunk = false
   suppress_doc_rag_lru = true
   reason = blocked_by_memory_intent
   ```

5. 其他模糊问题：
   - 例如 `agent runtime 是什么？`
   - 不预加载 Document RAG。
   - 模型仍可通过 `tool_search` 找到工具。

## LRU 残留处理

审阅指出的关键风险：

```text
上一轮调用过 search_docs 后，ToolDiscoveryState 可能把 search_docs 放进该 session 的 LRU。
下一轮用户问“你还记得我之前说过什么吗？”时，即使本轮意图规则不预加载，LRU 仍可能让 search_docs 可见。
```

本计划采用：

```text
强记忆/session 意图且无强文档意图时，在当前 turn 临时从 effective_preloaded 中移除 search_docs / fetch_doc_chunk。
```

注意：

- 不删除 LRU。
- 不改 `ToolDiscoveryState`。
- 只影响当前 turn 的可见工具集合。

## 接入点

接入 `DefaultReasoner.run_turn()`：

```text
1. 读取 LRU preloaded。
2. 根据当前用户输入计算 doc_rag preload decision。
3. 生成 effective_preloaded：
   - 先加入 LRU preloaded。
   - 再加入 intent preload 工具。
   - 如果 suppress_doc_rag_lru=true，则从当前 turn effective_preloaded 中移除 search_docs/fetch_doc_chunk。
4. 把 effective_preloaded 传给本 turn 的 prompt 构建和 run。
5. 不写回 ToolDiscoveryState。
```

原因：

- `run_turn()` 能拿到当前用户消息文本。
- `run()` 只接收已经渲染后的 messages 和 preloaded tools，不适合做原始用户意图判断。

## 记录和可观测性

至少记录 logger：

```text
[tool_preload] doc_rag search_docs=yes fetch_doc_chunk=no suppress=no reason=strong_doc_intent matched=文档知识库
```

如果当前 turn trace 支持 extra/context 字段，则记录：

```json
{
  "doc_rag_preload": {
    "preload_search_docs": true,
    "preload_fetch_doc_chunk": false,
    "suppress_doc_rag_lru": false,
    "confidence": "high",
    "reason": "strong_doc_intent",
    "matched_terms": ["文档知识库"]
  }
}
```

如果 trace 字段改动成本较高，第一阶段至少记录 logger，并将 observe 字段扩展列入后续任务。

## 测试计划

### 单元测试

新增 `tests/test_doc_rag_intent.py`：

1. 强文档意图：

```text
请从文档知识库中检索 agent runtime 负责什么
```

预期：

```text
preload_search_docs=true
preload_fetch_doc_chunk=false
confidence=high
```

2. 文档引用但不展开：

```text
请从文档知识库中检索 agent runtime 负责什么？回答必须带文档引用
```

预期：

```text
preload_search_docs=true
preload_fetch_doc_chunk=false
```

3. 原文证据：

```text
请从文档知识库中检索 agent runtime 负责什么？请展开原文证据
```

预期：

```text
preload_search_docs=true
preload_fetch_doc_chunk=true
```

4. 模糊架构问题：

```text
agent runtime 是什么？
```

预期：

```text
preload_search_docs=false
```

5. fresh 记忆问题：

```text
你还记得我学习 agent 时关注什么方向吗？
```

预期：

```text
preload_search_docs=false
suppress_doc_rag_lru=true
```

6. 冲突：只从文档：

```text
只从文档知识库回答，不要使用长期记忆：agent runtime 是什么？
```

预期：

```text
preload_search_docs=true
suppress_doc_rag_lru=false
```

7. 冲突：只从长期记忆：

```text
只从长期记忆回答，不要查文档：agent runtime 是什么？
```

预期：

```text
preload_search_docs=false
suppress_doc_rag_lru=true
```

### 集成测试

重点覆盖：

- fresh 文档问题：初始 visible tools 包含 `search_docs`，不需要 `tool_search`。
- 强文档 + 原文证据：初始 visible tools 包含 `search_docs` 和 `fetch_doc_chunk`。
- fresh 记忆问题：不因意图规则预加载 `search_docs`。
- memory-after-doc-LRU：同 session 上一轮调用过 `search_docs`，下一轮强记忆问题应在当前 turn 临时压掉 doc_rag LRU 可见性。

集成测试应落在 `DefaultReasoner.run_turn()` 附近，而不是只测 `run()`。

## 回归测试

建议命令：

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_doc_rag_intent.py \
  tests/test_doc_rag_tools.py \
  tests/test_doc_rag_toolset.py \
  tests/test_doc_rag_citation_plugin.py \
  tests/test_citation_plugin.py \
  tests/test_plugin_manager.py -q
```

如果改到 `DefaultReasoner.run_turn()`，还需补跑相关 passive turn / reasoner 测试。

## Live Smoke 验收

1. disabled 文档问题：

```text
请从文档知识库中检索 agent runtime 负责什么？回答必须带文档引用
```

预期：

```text
search_docs -> final
```

不应出现：

```text
tool_search
read_file
list_dir
shell
```

2. enabled 简单文档问题：

```text
请从文档知识库中检索 agent runtime 负责什么？
```

预期：

```text
search_docs -> final
```

3. enabled 原文证据问题：

```text
请从文档知识库中检索 agent runtime 负责什么？请展开原文证据并带引用
```

预期：

```text
search_docs -> fetch_doc_chunk -> final
```

4. 记忆问题：

```text
你还记得我学习 agent 时关注什么方向吗？
```

预期：

```text
不预加载 search_docs
不因为上一轮 RAG 工具 LRU 残留而暴露 search_docs
```

## 风险和取舍

- 漏预加载可以接受：模型仍可通过 `tool_search` 找工具，最多多一轮。
- 误预加载更危险：可能把记忆/session 问题导向文档 RAG，所以规则保持保守。
- 不做 LLM classifier：避免引入额外成本和不稳定性。
- 不改 always-on：保持工具空间干净。
- LRU suppression 是当前 turn 层面的保护，不是清理用户历史工具使用记录。

## 阶段性验收

第一阶段只要求：

- 明确文档知识库问题必须预加载 `search_docs`。
- 明确原文/证据展开的文档问题必须预加载 `fetch_doc_chunk`。
- 强记忆/session 问题不得因为新规则或 LRU 残留暴露 Document RAG 工具。
- observe/log 能解释本轮为什么预加载或压制 Document RAG 工具。
