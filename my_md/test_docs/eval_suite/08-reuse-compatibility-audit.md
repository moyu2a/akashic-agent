# Existing Eval Runner Compatibility Audit

日期：2026-08-06

本文是 Agent Evaluation Harness v2 的前置审查。旧程序只有在确认输入、输出、runtime、trace 和报告契约匹配后，才能接入统一 runner。

## 状态定义

| 状态 | 含义 |
| --- | --- |
| `MATCH` | 当前接口和语义可以直接复用。 |
| `ADAPTER_REQUIRED` | 核心逻辑可复用，但必须通过 adapter 转换接口或报告。 |
| `STALE` | 只能作为历史参考，不能进入当前主 gate。 |
| `DO_NOT_REUSE` | 与当前运行时或安全边界不匹配，禁止接入。 |

## 审查基线

| 组件 | 当前版本基线 | 已有产出 | 初始判断 |
| --- | --- | --- | --- |
| `live_eval_runner.py` | `df566c9`, 2026-07-07 | live Markdown report、observe/tool evidence | `ADAPTER_REQUIRED` |
| `deep_live_eval_runner.py` | `df566c9`, 2026-07-07 | deep live JSON/Markdown reports、规则/judge 结果 | `ADAPTER_REQUIRED` |
| `offline_trace_eval.py` | `df566c9`, 2026-07-07 | offline score report | `ADAPTER_REQUIRED` |
| `memory2/eval_runner.py` | `7ee506b`, 2026-08-02 | memory offline eval reports | `ADAPTER_REQUIRED` |
| `memory2/eval_comprehensive_online.py` | `7bb3b06`, 2026-07-28 | real LLM memory answer reports | `ADAPTER_REQUIRED` |
| `agent/optimization/real_ab_run.py` | `d80e74a`, 2026-08-05 | cost/latency A/B reports | `ADAPTER_REQUIRED` |
| `eval/longmemeval` | 2026-04-18 baseline | LongMemEval results | `ADAPTER_REQUIRED` |
| `eval/personamem` | 2026-04-19 baseline | PersonaMem results | `ADAPTER_REQUIRED` |
| tool governance evaluator | `f33a740`, 2026-08-05, branch only | 60-turn real LLM governance report | `ADAPTER_REQUIRED` |
| `miniroute/evaluation/evaluate.py` | main branch current | route accuracy and risk metrics | `ADAPTER_REQUIRED` |

以上判断是初始状态，不代表已完成接入。每个组件还必须通过 contract tests。

## 必查契约

### Runtime API

- `AgentLoop.process_direct()` 参数和返回值。
- `DefaultReasoner.run_turn()` 参数。
- `TurnRunResult` 字段。
- `tool_chain` 结构。
- `context_retry`、`react_stats`、`tool_boundary` 字段。

### 数据和 Trace

- `observe.db` turns schema。
- `tool_audit.db` policy action/reason 字段。
- `sessions.db` session key 格式。
- memory2 数据表。
- approval lifecycle 字段。
- redaction 和 audit 字段。

### Usage 和延迟

- prompt/completion/total token 是否由真实 provider 返回。
- cache token 是否可用。
- provider error、timeout、environment error 是否可区分。
- fake usage 是否被错误当作真实成本。

### 隔离和生命周期

- runtime 是否正确 start/stop。
- workspace 是否按 episode 隔离。
- session 是否能 reset。
- resume 是否复用错误状态。
- 多轮 case 是否污染后续 case。

## 接入规则

每个旧 runner 接入时必须提供：

1. 输入转换器：旧 case -> `TaskSpec`。
2. 执行适配器：旧 runtime -> `AgentAdapter`。
3. 事件转换器：旧 trace -> unified event。
4. 结果转换器：旧 report -> unified report。
5. contract tests。
6. privacy tests。

没有 adapter 的旧 runner 不得直接被统一 runner import。

## 可信边界

- 旧报告可以作为历史基线，但不能自动视为当前代码结果。
- 旧 runner 的 token/latency 只有在确认 usage 字段来源后才能进入成本结论。
- 旧 runner 的 judge 结果不能覆盖 deterministic safety gate。
- MiniRoute 当前处于调试阶段，只审查 schema 和评测输出，不接入生产。
