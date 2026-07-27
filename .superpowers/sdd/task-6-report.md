# Task 6 Report: Executor and Status Command Integration

## What I Implemented

- Extended managed side-effect payload registration to include `shell` so deferred shell approvals store the full payload only in the private payload vault.
- Updated `ToolExecutor` to recognize all managed side-effect tools, block any direct trusted shell approval with `approved_side_effect_requires_managed_apply`, and redact shell command values from defer/deny policy and audit traces.
- Routed status-command prepare, apply, and rollback requests by approval-record tool type: file tools use `ApprovedSideEffectRuntime`; shell uses `ApprovedShellSideEffectRuntime`.
- Added injectable `shell_sandbox_runner` support and initialized the plugin with `DockerPodmanSandboxRunner.find_available()`.
- Added normalized `sandbox_backend` to emitted approved-side-effect lifecycle metadata.
- Documented Docker/Podman requirements, shell redaction, and unsupported shell rollback.

## Tests and Results

- `PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_tool_executor_approval_workflow.py tests/test_status_commands_approved_side_effects.py -q -p no:cacheprovider`
  - PASS: 16 passed.
- `PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_approved_shell_side_effect_runtime.py -q -p no:cacheprovider`
  - PASS: 15 passed.
- `git diff --check`
  - PASS: no whitespace errors.

## TDD Evidence

RED command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_tool_executor_approval_workflow.py::test_executor_records_shell_payload_and_blocks_direct_approved_shell tests/test_status_commands_approved_side_effects.py::test_run_approved_tool_shell_uses_sandbox_runtime_without_raw_command -q -p no:cacheprovider
```

Result: 2 failures, as expected.

- Executor test failed because shell was not stored by `record_managed_side_effect_payload()`.
- Status-command test failed because `ToolApprovalCommandModule` did not accept `shell_sandbox_runner`.

GREEN focused result: the two specified tests plus the destructive-shell redaction test passed (3 passed). The final suites above remain green.

## Files Changed

- `agent/tool_hooks/executor.py`
- `plugins/status_commands/plugin.py`
- `plugins/status_commands/README.md`
- `tests/test_tool_executor_approval_workflow.py`
- `tests/test_status_commands_approved_side_effects.py`
- `agent/policies/tool_approval_runtime.py`

## Self-Review

- Confirmed deferred shell output, policy trace, audit trace, and approval database exclude the raw shell command in executor coverage.
- Added destructive-shell denial coverage asserting the raw command is absent from output, policy trace, and audit trace.
- Confirmed status apply reply and metadata exclude raw command text, `stdout_text`, `stderr_text`, and `payload_path`.
- Focused production greps found no literal test command and no forbidden output/payload fields in executor or status-command modules.
- Shell resource-policy metadata is already sanitized by `ApprovedShellSideEffectRuntime`; status commands do not serialize runtime result metadata into replies.

## Concerns

- The task's owned-file list excluded `agent/policies/tool_approval_runtime.py`, but its file-only guard prevented the required executor/status shell payload workflow. I made the minimal two-line shared-runtime correction and will include it in the implementation commit; omitting it would cause the Task 6 status shell scenario to fail.

## Pre-Hook Denial Red/GREEN Fix

RED command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_tool_executor_approval_workflow.py::test_executor_redacts_shell_pre_hook_denial_reason -q -p no:cacheprovider
```

RED result: `1 failed`. The denial output was `blocked command: echo secret-token`, confirming the raw shell command leaked from the pre-hook reason.

GREEN focused command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_tool_executor_approval_workflow.py::test_executor_redacts_shell_pre_hook_denial_reason tests/test_status_commands_approved_side_effects.py::test_rollback_tool_shell_is_unsupported_without_raw_command_leakage -q -p no:cacheprovider
```

GREEN focused result: `2 passed in 0.29s`.

Covering command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_tool_executor_approval_workflow.py tests/test_status_commands_approved_side_effects.py tests/test_approved_shell_side_effect_runtime.py -q -p no:cacheprovider
```

Covering result: `33 passed in 2.12s`.

`git diff --check` result: PASS (no whitespace errors).

The shell pre-hook denial path now returns a generic denial output and redacts hook reasons and extra messages. Non-shell pre-hook denial behavior remains unchanged. Added shell rollback coverage confirms `rollback_not_supported_for_shell` is returned without command leakage in the reply or lifecycle metadata.

## Re-review RED Evidence

RED command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_tool_executor_approval_workflow.py::test_executor_records_shell_payload_and_blocks_direct_approved_shell tests/test_tool_executor_approval_workflow.py::test_executor_redacts_denied_destructive_shell_command tests/test_tool_executor_approval_workflow.py::test_executor_redacts_shell_pre_hook_exception tests/test_tool_executor_approval_workflow.py::test_preflight_redacts_shell_pre_hook_exception tests/test_status_commands_approved_side_effects.py::test_prepare_tool_shell_routes_to_sandbox_runtime_without_raw_command tests/test_status_commands_approved_side_effects.py::test_run_approved_shell_fails_closed_without_runner_without_raw_command -q -p no:cacheprovider
```

RED result: `4 failed, 2 passed in 0.41s`.

- Deferred and destructive-deny shell results exposed the raw command through `final_arguments`.
- `execute()` and `preflight()` exposed raw shell commands through interpolated pre-hook exception messages.

## Re-review GREEN Evidence

Focused GREEN command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_tool_executor_approval_workflow.py::test_executor_records_shell_payload_and_blocks_direct_approved_shell tests/test_tool_executor_approval_workflow.py::test_executor_redacts_denied_destructive_shell_command tests/test_tool_executor_approval_workflow.py::test_executor_redacts_shell_pre_hook_exception tests/test_tool_executor_approval_workflow.py::test_preflight_redacts_shell_pre_hook_exception tests/test_status_commands_approved_side_effects.py::test_prepare_tool_shell_routes_to_sandbox_runtime_without_raw_command tests/test_status_commands_approved_side_effects.py::test_run_approved_shell_fails_closed_without_runner_without_raw_command -q -p no:cacheprovider
```

Focused GREEN result: `6 passed in 0.36s`.

Covering GREEN command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_tool_executor_approval_workflow.py tests/test_status_commands_approved_side_effects.py tests/test_approved_shell_side_effect_runtime.py -q -p no:cacheprovider
```

Covering GREEN result: `37 passed in 2.18s`.

The executor now exposes an empty `final_arguments` mapping for shell results while retaining raw shell arguments internally through policy evaluation and private vault capture. Shell pre-hook exceptions produce generic output and redact accumulated hook traces and messages. Status-command coverage confirms shell prepare routing and unavailable-runner fail-closed behavior without raw command leakage; unavailable execution leaves the approval approved for retry.

`git diff --check` result: PASS (no whitespace errors).
