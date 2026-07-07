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

## 后续补充模板

| ID | 类型 | 状态 | 优先级 | 问题 | 影响 | 关联文档 |
| --- | --- | --- | --- | --- | --- | --- |
| EV-xxx |  | open |  |  |  |  |
