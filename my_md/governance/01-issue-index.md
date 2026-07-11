# Issue Index

这个文档记录项目当前已发现的问题、风险和演进方向。它不是普通测试日志，而是面向后续修复和面试表达的技术债总表。

## 问题状态

| 状态 | 含义 |
| --- | --- |
| open | 已确认存在，尚未修复 |
| investigating | 需要进一步验证 |
| test-noise | 测试集或断言误判 |
| fixed | 已修复，等待或已经回归验证 |
| deferred | 暂缓处理 |

## 当前问题总表

| ID | 类型 | 状态 | 优先级 | 问题 | 影响 | 关联文档 |
| --- | --- | --- | --- | --- | --- | --- |
| EV-001 | memory | open | P0 | 临时 session 信息可能被写入长期记忆 | 造成跨 session 看似泄漏，污染长期记忆 | [02-current-issues.md](./02-current-issues.md) |
| EV-002 | tool-governance | open | P0 | 用户明确要求不用工具时，模型仍可能调用工具 | 违反用户约束，影响安全和成本 | [02-current-issues.md](./02-current-issues.md) |
| EV-003 | cost | open | P1 | 简单任务可能触发过长工具链 | 增加延迟、token 和工具调用成本 | [02-current-issues.md](./02-current-issues.md) |
| EV-004 | eval | test-noise | P0 | 部分测试断言过硬，把正确行为判为失败 | 干扰真实问题定位 | [02-current-issues.md](./02-current-issues.md) |
| EV-005 | eval-infra | open | P1 | judge 依赖环境不完整时会跳过语义评审 | 报告缺少 LLM judge 判断 | [02-current-issues.md](./02-current-issues.md) |
| EV-006 | session-isolation | open | P0 | `fetch_messages` 可能跨 session 回源到其他会话内容 | 私有会话内容被错误用于当前 session 回答 | [02-current-issues.md](./02-current-issues.md) |
| RAG-005 | rag-config/tool-governance | fixed | P1 | Document RAG live smoke 中 `doc_rag.enabled=false`，`search_docs` 返回 disabled 后模型继续 fallback 到 `read_file`；第一阶段已增强 disabled 工具语义，live smoke 待验证 | P9 真实链路无法验证 citation，且 disabled 场景产生无效工具链 | [02-current-issues.md](./02-current-issues.md) |
| RAG-006 | rag-tool-governance/cost | open | P1 | Document RAG 启用后 live smoke 仍出现 7 轮 ReAct；已形成经审阅的 P10 方案：强文档意图做 turn-local 预加载，强记忆/session 意图临时压制 doc_rag LRU 残留，不改 always-on | 增加延迟、token、工具调用成本；若不压制 LRU，还可能把记忆问题误导到文档检索 | [02-current-issues.md](./02-current-issues.md), [../rag/19-document-rag-p10-intent-preload-plan.md](../rag/19-document-rag-p10-intent-preload-plan.md) |
| RAG-007 | rag-citation/faithfulness | open | P1 | Document RAG citation 来源有效，但部分结论属于标题结构推断，证据支撑强度不足 | citation valid 不等于答案忠实，可能被 judge 判为 evidence weak | [02-current-issues.md](./02-current-issues.md) |

## 后续补充模板

| ID | 类型 | 状态 | 优先级 | 问题 | 影响 | 关联文档 |
| --- | --- | --- | --- | --- | --- | --- |
| EV-xxx |  | open |  |  |  |  |
