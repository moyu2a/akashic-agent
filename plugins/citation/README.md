# citation 插件

记忆引用追踪协议。在系统 prompt 中注入引用规范，从 LLM 回复里提取引用的记忆 ID，并清理协议标签。

---

## 接入点

| 接入方式 | 阶段 |
|---|---|
| `prompt_render_modules()` | `prompt_render.emit` 之后——注入引用协议文本 |
| `after_reasoning_modules()` | `after_reasoning.build_ctx` 之后——提取 cited ID |
| `after_reasoning_modules()` | `after_reasoning.emit` 之后——清理残留协议标签 |

---

## 运作逻辑

### 1. 注入引用协议（CitationPromptModule）

每轮推理前，在系统 prompt 底部追加一段隐藏指令（`_CITATION_PROTOCOL`），要求 LLM 在用到记忆条目时，在回复末尾输出 `§cited:[id1,id2]§` 格式的引用行，且不向用户暴露这行的存在。

### 2. 提取 cited ID（CitationAfterReasoningModule）

推理完成后，用正则扫描 `reply` 尾部，匹配 `§cited:[...]§` 标签：

- 若匹配成功，提取 ID 列表，写入 `persist:assistant:cited_memory_ids` slot，并把标签从 reply 中剥除。
- 若 reply 里没有引用行，fallback 到工具调用链：扫描 `recall_memory` 工具的返回结果，从 JSON 里取出 `cited_item_ids` 或 `items[].id`，作为本轮引用 ID。

提取到的 ID 由下游持久化模块写入数据库，用于更新记忆条目的被引用计数和时间戳。

### 3. 清理协议标签（ProtocolTagCleanupModule）

在 persist 之前再做一次扫描，用正则清除 reply 末尾所有残留的 `<tag:value>` 形式协议标签（包括其他插件可能留下的），保证对外输出的文本干净。

### 4. Document RAG 引用校验（DocRagCitationValidatorModule）

Document RAG 引用是对用户可见的来源引用，格式为 `[source_path > heading_path]`。
它只允许来自当前轮 `search_docs` / `fetch_doc_chunk` 工具结果中的 `citation` 字段。

- 记忆引用使用内部协议 `§cited:[id]§`，不会展示给用户。
- Document RAG 引用使用可见协议 `[source_path > heading_path]`，用于回答文档知识库问题。
- 当全局配置 `app_config.doc_rag.enabled=true` 时，插件才会向系统 prompt 注入 Document RAG 引用规则。
- 如果最终回复里出现当前轮工具结果没有返回过的文档引用，插件会移除该引用，并把移除记录写入 `outbound_metadata["doc_rag_citation"]`。
- 如果使用了 Document RAG 工具证据但回复漏掉引用，插件会追加 `参考来源：...`，引用来自当前轮工具结果。
- 如果文档知识库无命中，或回复明确表示没有足够文档证据，插件不会编造引用。
