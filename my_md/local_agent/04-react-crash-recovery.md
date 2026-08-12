# 普通 ReAct 崩溃恢复设计

## 目标

普通对话里的 ReAct loop 不再只依赖内存状态。模型 step、普通工具调用、工具结果和最终回复边界会写入 `sessions.db`，进程崩溃后由启动恢复服务接管未完成 turn。

## 存储位置

- `sessions.db.turn_runs`: 一次普通 ReAct turn 的运行状态，包含 `lease_owner`、`lease_expires_at`、`current_step_id` 和 `status`。
- `sessions.db.react_steps`: 每一轮模型调用边界，保存 `model_input_json`、assistant tool calls、tool result 引用和 step 状态。
- `sessions.db.tool_invocation_attempts`: 普通工具调用 attempt，保存工具名、参数 hash、`recovery_ref`、幂等/副作用标记、lease 和结果消息引用。
- `sessions.db.messages`: 保存工具结果消息、最终 assistant 消息和流式残片。
- `sessions.db.outbox`: 只保存出站消息引用，不保存正文；正文仍在 `messages`。

## 恢复规则

- 启动后先加载插件和工具，再运行普通 ReAct recovery，避免恢复推理时缺少插件工具或 hook。
- 恢复服务必须先 claim `turn_runs` 的 Turn 级 lease；没有抢到 lease 的 worker 不能进入 step/tool 恢复。
- `tool_running` 且工具只读/幂等时，attempt 回到 `pending`，允许后续安全重试。
- `tool_running` 且工具有不可确认外部副作用时，turn 和 attempt 标记为 `blocked`，不自动重放。
- `tool_succeeded` 时，用 `ReactReplayBuilder` 重建 messages，然后调用 `AgentLoop.resume_react_turn()` 继续下一轮模型推理。
- replay 时严格校验 assistant `tool_calls[].id` 和后续 `tool_call_id` 匹配；不匹配直接 blocked。
- 如果原 user message 尚未 commit，replay 使用 `react_steps.model_input_json` 作为基础上下文，避免恢复后丢失原始 prompt/context。
- 最终回复仍走 `post_reasoning -> after_turn -> PersistentOutboundPort`，保持 `messages + outbox` 的既有持久化和派发路径。

## Turn 阶段恢复矩阵

一次普通 ReAct turn 的主要阶段都有明确的崩溃恢复策略。恢复服务先抢 `turn_runs` 的 lease，再按当前 step/tool/message 状态决定继续、重试或 blocked。

| 崩溃位置 | 重启后的处理 |
| --- | --- |
| `turn created` / `model_pending` | claim Turn lease 后重试当前模型 step。 |
| `model_running` | 不做 token 级续传；使用已持久化的 `model_input_json` 重新执行该模型 step。 |
| 流式 generation 中 | 保留已写入的 partial content，将未完成 generation 标记为 `aborted`，不续传同一个 LLM stream。 |
| assistant `tool_calls` 已持久化 / `tool_pending` | 保留原始 `tool_call_id`、工具名和参数；不伪造 tool result，恢复后按普通工具 checkpoint 继续执行。 |
| `tool_running` 且工具只读或幂等 | lease 过期后将 attempt 放回 `pending`，允许安全 retry。 |
| `tool_running` 且工具有不可确认外部副作用 | 将 attempt 和 turn 标记为 `blocked`，不自动 replay，等待人工处理或工具提供可 probe 的 `recovery_ref`。 |
| `tool_succeeded` | replay assistant tool call 和 tool result；严格校验 `tool_call_id` 匹配后，通过 `AgentLoop.resume_react_turn()` 进入下一轮 reasoning。 |
| replay 协议无效 | 将 turn 标记为 `blocked`，避免把顺序错乱或 ID 丢失的上下文发给模型。 |
| `final_pending` | 将 turn 标记为 completed；最终消息投递交给 `outbox` 恢复。 |
| assistant message 已落库，`outbox` 为 `pending` / `sending` / `unknown` | 由 outbox reconciler 根据派发状态重试、查询远端状态、转为 `sent` 或 `failed`。 |
| recovery callback 失败 | 当前 turn 标记为 `blocked`，记录 `resume_failed`，恢复服务继续处理其他 turn。 |

一句话原则：能证明安全的自动重试，结果已经落库的从结果之后继续，不确定外部副作用的一律 blocked，最终消息投递由 outbox 兜底。

## 边界

- 不做 LLM stream 的 token 级续传；未完成 generation 仍按现有逻辑标记 aborted，并保留 partial content。
- 不对不可确认副作用工具自动重试。需要工具提供可 probe 的 `recovery_ref` 后，才能进一步自动闭环。
- 恢复 turn 使用 `omit_user_turn=true`，避免重复写入用户消息；使用 `skip_post_memory=true`，避免启动恢复产生额外记忆写入副作用。

## Gate

- storage/lease/schema gate: `tests/test_react_recovery_storage.py`
- ordinary tool checkpoint gate: `tests/test_ordinary_tool_checkpoint.py`
- ReAct step persistence gate: `tests/test_react_step_persistence.py`
- replay protocol gate: `tests/test_react_replay_builder.py`
- startup recovery gate: `tests/test_react_recovery_startup.py`
- crash boundary gate: `tests/test_react_recovery_crash_injection.py`
- real resume wiring gate: `tests/test_react_turn_resume.py` 和 `tests/test_bootstrap_wiring_p2.py`
