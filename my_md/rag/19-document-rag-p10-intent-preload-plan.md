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
