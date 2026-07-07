# Future Automation Plan

这个文档记录如何把当前手工 eval suite 自动化。

## 目标形态

最终希望得到：

```text
eval_cases.yaml / large-eval-cases.yaml
-> eval_runner.py
-> 发送 CLI 消息
-> 等待 observe.db 出现新 turn
-> 自动解析 tool_calls / recall_inspector / sessions.db / memory2.db
-> 自动打分
-> 输出 score_report.md
```

## 自动化阶段

### Phase 0：测试集分层

保留两套 YAML：

```text
01-eval-cases.yaml        小测试集，适合快速回归
large-eval-cases.yaml     大测试集，适合阶段性评估
```

runner 需要支持按字段过滤：

```text
priority: P0 / P1 / P2
execution_mode: live / offline / future
risk_level: safe / guarded
category: passive_loop / memory / safety / document_rag 等
```

默认执行策略：

```text
先跑 P0 + live + safe
再跑 offline
guarded 需要显式确认
future 只生成未实现报告，不计入当前失败
```

### Phase 1：只做离线评分

不自动发送消息，只读取已有 observe.db。

输入：

```text
case_id -> turn_id 映射
```

输出：

```text
每个 case 的工具调用、最终回答、pass/fail
```

优点：

- 风险低。
- 不影响当前 agent。
- 可以复用已经做过的 23 条测试。

### Phase 2：半自动执行

脚本读取 YAML，提示用户手动复制输入到 CLI，然后自动检测最新 turn。

优点：

- 不需要改 CLI 协议。
- 仍然可以积累结构化报告。

### Phase 3：全自动执行

脚本直接连接 `/tmp/akashic.sock`，发送消息并等待响应。

需要处理：

- 多 session 创建。
- 等待后台任务。
- 等待 scheduler。
- 清理测试数据。
- 防止危险 case 误执行。
- 支持从 `large-eval-cases.yaml` 中跳过 `guarded` 和 `future`。
- 支持多 session case 的独立 session 创建与回收。

### Phase 4：CI / 回归测试

把安全的 case 加入 CI：

```text
基础问答
session history
工具错误处理
memory mock
tool_search mock
shell_safety mock
```

不适合 CI 的 case：

```text
真实 LLM 调用
真实 sudo / rm
真实 Telegram / QQ 推送
真实 proactive 推送
```

### Phase 5：大测试集报告

针对 `large-eval-cases.yaml` 输出分组报告：

```text
总通过率
P0 通过率
Agent 工程通过率
RAG / Memory 通过率
安全治理通过率
工具正确率
记忆准确率
RAG 证据命中率
平均工具调用次数
平均 agent loop 轮数
平均 prompt tokens
高风险失败列表
已知回归列表
future case 待实现列表
```

这样可以把测试结果直接转化成项目优化路线。

## 自动评分规则建议

### 工具调用匹配

```text
must_include: 所有工具都出现则 pass
must_not_include: 任一禁用工具出现则 fail
expected: 完全匹配则 pass，额外工具记 partial
```

### 回答内容匹配

```text
final_answer_contains: 全部出现则 pass
final_answer_contains_any: 任一出现则 pass
final_answer_not_contains: 任一出现则 fail
```

### 记忆状态检查

```text
memory_items.status == active
old memory status == superseded
source_ref 非空
```

### RAG 证据检查

```text
recall_memory.items[0].id == expected_id
source_ref == expected_source_ref
fetch_messages 被调用
最终回答没有违背原文
```

### 成本检查

初期只做软指标：

```text
tool_call_count <= expected_max
iteration_count <= expected_max
```

后续再接 token：

```text
input_tokens
prompt_tokens
cache_hit_rate
latency_seconds
```

## 面试表达

可以这样介绍：

```text
我没有只做功能 demo，而是为 agent 建了一套 eval suite。
它覆盖任务成功率、工具轨迹、安全拦截、记忆准确性、session 隔离、RAG 证据链和成本指标。
第一阶段是手工可解释测试，第二阶段计划通过 observe.db 和 YAML case 自动评分。
```
