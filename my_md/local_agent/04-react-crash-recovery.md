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
