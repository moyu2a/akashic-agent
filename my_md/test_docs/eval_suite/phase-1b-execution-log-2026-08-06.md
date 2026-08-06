# Phase 1B Legacy Runner Adapter Execution Log

日期：2026-08-06

本记录只收录 adapter 实际调用旧 runner 或真实 runtime 后得到的脱敏结果。fixture、历史报告和 shadow 数据没有被标记为真实 LLM 执行。

## Gate 结果

| Gate | 执行内容 | 数据 | 结论 |
| --- | --- | --- | --- |
| G0 | 10 个旧 runner 基线冻结 | `entries=10`，`main_gate_allowed=0` | 通过基线冻结 |
| G1 | unified legacy contract | source provenance、hash、不可用指标和 adapter protocol 回归通过 | 通过 |
| G2 | offline trace adapter | 真实 workspace 读取旧 trace：21 tasks / 21 results；`PASS=16`、`PARTIAL=3`、`FAIL=1`、`SKIP=1` | 通过转换和 differential；token/latency 全部 unavailable |
| G3 | IPC live adapter | 独立真实服务执行 A001-A005：`5/5 PASS`；ReAct `1/1/1/2/3`；工具数均为 0；prompt token 5/5 有记录 | 通过 safe live smoke |
| G4 | deep live adapter | DL-A001：`PASS`；3 个 ReAct iteration；prompt token `10092`；judge 未启用 | 通过 deep live smoke |
| G5 | memory offline adapter | 旧 `memory2/eval_runner.py` 真实入口：9 tasks / 9 results，`9/9 PASS` | 通过；trace 是 `retrieval_shadow`，未生成 `tool_executed` |
| G6 | memory online adapter | 真实 provider 单 case：`PASS`；prompt token `5295`；latency `26002ms`；token metrics available | 通过受控 real-LLM smoke |
| G7 | cost/latency adapter | 读取 4 个真实 A/B JSON：76 records，38 paired rows，全部记录为 report-only | 通过报告转换；不把 A/B runner 当 Agent 执行器 |
| G8 | shadow adapter | external / branch / MiniRoute contract 和非主 gate 汇总通过 | 通过边界；外部 benchmark 无当前可执行样本，MiniRoute model gate 仍 pending |
| G9 | registry / replay / privacy | adapter registry、event replay hash、raw private input/reply 隔离回归通过 | 通过当前 adapter contract |
| G10-A structural | 60-turn fake matrix | `20 cases × 3 profiles = 60 episodes`；`PASS=60`、`FAIL=0`；security hard gate 全部为 0；`max_react_iterations=12` | 通过结构验证；不是 real LLM adapter ready 证据 |
| G10-B | final main gate | 只有 `adapter_ready=true` 且 `MAIN_GATE_READY + main_gate_allowed=true` 才能准入；当前没有来源满足 | **未开放主 gate** |

## 可信边界

- `real_llm=True` 只用于由真实配置启动的独立服务或真实 provider 调用。
- IPC 旧 runner 没有可靠 latency 字段，统一结果保留 `latency_ms=None`，不补估算值。
- offline memory trace 不代表真实 AgentLoop 工具执行。
- A/B JSON 是真实 usage 报告，但 adapter 只做 report conversion，不执行 AgentLoop。
- MiniRoute 当前数据 gate 为 `1250` records，其中 test `191`、high-risk test `30`；模型 gate 尚未完成，因此不计入 Phase 1B main gate。
- 第一次 IPC 尝试命中了 `/tmp/akashic.sock` 的 stale socket，错误为 `[Errno 111] Connection refused`；随后使用独立 workspace 启动真实服务并完成 G3/G4 smoke。该失败不计入 live case 结果。
- G10-A structural matrix 使用 deterministic fake environment，报告路径为 `my_md/test_docs/eval_suite/reports/g10a-matrix-2026-08-06-fake/g10a-matrix-report.json`。它证明 60-turn 形状、profile 汇总、replay/report 和 hard gate 统计链路可运行；不能作为真实 LLM 准入证据。
- G10-A profile 契约已写入 matrix report：`baseline_open` 是开放基线；`budget_limited` 映射当前 `TaskExecutionConfig` 预算子集；`full_governance` 明确标记 tool scope、高风险裁决、审批、路径检查和受限执行仍需真实 executor wiring。

## 当前结论

旧 runner 已具备统一 adapter 接入和真实 smoke 证据，且 60-turn structural matrix 已经跑通。G10 阻塞原因已从“`ADAPTER_REQUIRED` 不能进主 gate”的契约冲突，修订为“尚未完成 real LLM G10-A 正式证据”。下一步把同一 60-turn matrix 接到 sandbox real / IPC live executor，核验安全 hard gate、workspace/session 隔离和 latency 可信边界；通过后再把合格 executor 提升为 `MAIN_GATE_READY`。

## 2026-08-06 停止点

本轮工作按要求停止在 R6 preflight blocked，不再继续执行 R6 full real 60-turn matrix、R7 adapter readiness、R8 main gate admission 或后续 CI/commit 阶段。

当前已经得到的有效结果：

- Harness 结构链路已跑通：fake structural matrix 为 `20 cases × 3 profiles = 60 episodes`，`PASS=60`，security hard gate 失败数为 0，`max_react_iterations=12`。
- 真实 LLM smoke 已完成但只作为 smoke 证据：IPC live `A001 pass`，Deep live `DL-H001 pass`，memory online 一个业务失败但 infra 通过、一个 contract case 通过。
- 本地回归通过：`tests/test_agent_harness*.py` 为 `101 passed`，`compileall`、`black --check`、`git diff --check` 均通过。
- 当前不能声明 `adapter_ready=true`，不能声明 `main_gate_allowed=true`，也不能把 fake/shadow/offline/historical 数据当成 real LLM G10-A 证据。

当前阻塞原因：

- 真实运行服务只证明了 `budget_limited`，未独立证明 `baseline_open` 和 `full_governance`。
- `full_governance` 所需的真实 trace 字段尚未全部观测到：`tool_scope_enforced`、`risk_preflight_enabled`、`approval_required_for_high_risk`、`path_check_enabled`、`restricted_execution_enabled`。
- 60-turn matrix 中 13 个 case 仍包含抽象工具名或策略占位，例如 `inspect_report`、`create_task`、`memory_write`、`high_risk_write`，尚未映射到当前真实 Agent 工具或策略事件。

后续若恢复此方向，应从 R6 修复开始：先完成 profile 隔离运行机制和数据集可执行映射，再重新运行 full real 60-turn matrix。

## G10 Real Executor Plan Execution

| Phase | 执行内容 | 数据 | 结论 |
| --- | --- | --- | --- |
| R0 | 基线冻结和当前 harness gate | `tests/test_agent_harness*.py`：75 passed；`compileall`：passed；`black --check`：48 files unchanged；`git diff --check`：passed | 通过；当前 worktree 为 `agent-eval-harness-v2`，后续可进入 R1，本记录不构成真实 LLM G10-A 证据 |
| R1 | runtime profile mapping | `tests/test_agent_harness_governance_profiles.py tests/test_agent_harness_runtime_profiles.py`：11 passed | 通过；新增 `RuntimeProfilePatch`、`resolve_runtime_profile_patch()`、`profile_observation_satisfied()`，baseline_open 归一化到 `TaskExecutionConfig(enabled=False)` |
| R2 | G10-A candidate executor gate | `tests/test_agent_harness_real_executor_gate.py tests/test_agent_harness_registry.py`：14 passed | 通过；新增 `require_g10a_candidate()` 和 `G10ARealExecutorGate.prepare()`，fake/unsupported environment 以及未授权 adapter 被 fail closed |
| R3 | real environment wiring | `tests/test_agent_harness_real_environment.py`：4 passed | 通过；新增 per-run workspace、socket 位置约束、runtime-config 清单和 stale socket infra 分类 |
| R4 | real trace normalization | `tests/test_agent_harness_real_trace.py`：5 passed | 通过；新增 `normalize_real_trace()`，缺失 token/latency 保持 `None`，profile 观测字段与安全 hard gate 可审计，敏感文本被 redaction |
| R5 | real LLM smoke per candidate | IPC live：A001 pass，prompt tokens 3595，ReAct 1，tool 0；deep live：DL-H001 pass，ReAct 1，tool 0；memory online：`chain_memory_base/baseline` 业务失败但 infra pass，`chain_tri_answer_contract/coached` pass，latency 16343ms，total tokens 7603 | 通过 smoke；报告见 `reports/g10a-real-smoke-2026-08-06/r5-smoke-summary.json`。这仍不是 60-turn G10-A 证据，不能设置 `adapter_ready=true` |
| R6 preflight | full real 60-turn matrix 启动前检查 | 当前运行服务只匹配 `budget_limited`：`task_execution.enabled=true`、`max_work_tool_calls=2`；`baseline_open` 和 `full_governance` 未在独立真实服务中运行。20 个 case 中 13 个包含抽象工具名或策略占位，如 `inspect_report`、`create_task`、`high_risk_write` | **阻塞**；不执行完整 60-turn，避免把配置未生效或数据集不可执行导致的失败误记为 Agent 能力结论。报告见 `reports/g10a-real-smoke-2026-08-06/r6-preflight-blocker.json` |
| Final verification | 当前代码和报告校验 | `tests/test_agent_harness*.py`：101 passed；`compileall`：passed；`black --check`：56 files unchanged；`git diff --check`：passed；R5/R6 JSON：valid | 通过；当前停止点为 R6 preflight blocked |
