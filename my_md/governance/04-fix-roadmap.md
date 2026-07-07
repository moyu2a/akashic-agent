# Fix Roadmap

这个文档记录后续修复优先级和验证方式。

## 修复优先级

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
