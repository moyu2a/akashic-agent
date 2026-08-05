# MiniRoute V1 Spec

## Goal

Build an offline-validated MiniMind SFT route model for MnemoAgent that classifies a single user message into intent, memory need, tool need, tool scope, and risk level.

## V1 Boundary

- Input: one user message only.
- Output: fixed JSON route result.
- No real tool execution.
- No memory write.
- No Shadow integration in V1.

## V1 Labels

- `intent`: `chat`, `memory_query`, `profile_update`, `task_plan`, `content_save`, `file_read`, `tool_execution`, `status_query`
- `risk_level`: `none`, `read_only`, `write`, `high_risk`
- `tool_scope`: `none`, `memory_tools`, `content_tools`, `file_read_tools`, `file_write_tools`, `shell_tools`, `task_tools`, `observe_tools`

## V1 Success Criteria

- JSON legality near perfect.
- High-risk recall must be conservative.
- Tool mis-open rate must be zero in evaluation.
- Offline data, training, and error analysis must all be reproducible in `miniroute/`.
