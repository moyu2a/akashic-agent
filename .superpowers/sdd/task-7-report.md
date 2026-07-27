# Task 7 Report: Execution Tools, Shared Toolset Wiring, Structured Outcomes, and Prompt Context

## Implementation

- Added five deferred, non-LRU TaskPlan execution control tools. They are service/orchestrator adapters only and do not issue SQL.
- Added immutable per-call `ToolExecutionContext`; registry execution merges it last without retaining its protected values in registry context. Execution adapters require that per-call context before accepting protected action, request, target, or attempt identifiers.
- Changed omitted registration risk to authoritative `unknown`, added defensive `get_risks_by_name()` snapshots, and passed the snapshot into `ToolAccessContext`. Built-in production registrations retain explicit risks; plugin tools without declared metadata remain unknown.
- Wired `TaskPlanToolsetProvider` with one `TaskPlanService` and one `TaskExecutionService` backed by the same store. The default `TaskExecutionConfig.enabled` remains false.
- Added bounded current-attempt prompt context, capped to 400 execution characters beyond the existing TaskPlan block. It exposes only attempt summary fields, not event/request payloads.
- Added `ToolResult.ok` and `error_code`; migrated `read_file` and `list_dir` to structured success/error outcomes while preserving their rendered text.
- Added invoker runtime facts to `ToolExecutionResult`, including explicit pre-hook, exception, normal-return, and preflight values. Registry re-raises execution-context tool errors so the executor records invocation failures accurately.

## TDD Evidence

### RED

Required focused command initially failed during collection as expected:

```text
ModuleNotFoundError: No module named 'agent.tools.execution_context'
```

### GREEN

Required focused command after implementation:

```text
42 passed in 1.30s
```

Adjacent execution, TaskPlan/access, filesystem, and plugin suite:

```text
350 passed in 10.38s
```

## Verification

- `git diff --check` passed.
- Targeted Ruff `F`/`E9` checks passed for Task 7 modules and tests. Shared legacy files still have pre-existing Ruff unused-import findings outside this change.
- Black check passed for new and newly formatted Task 7 modules/tests.
- `compileall` passed for Task 7 production modules.

## Concern

`tests/test_tool_access_gateway_reasoner.py::test_active_task_prompt_exposes_progress_task_tools` fails because `继续执行当前任务，更新下一步` is classified as `plan_inspect`, exposing only `inspect_task_plan`. The identical focused test also fails in a clean `ad07f60` archive, so it is a pre-existing TaskPlan intent-classification issue and is not included in this Task 7 commit.

## Corrective Review Fix

### RED

The review regressions failed before the corrective implementation:

```text
begin retry accepted forged model target/action through a partial execution context
finish/defer/abort accepted forged model attempt ids
ReadFileTool offset conversion raised ValueError instead of a ToolResult error
ToolBoundaryManager attempted to slice ToolResult and lost structured outcome state
TaskPlanToolsetProvider accepted mismatched execution stores
startup recovery failure left task execution controls registered
```

The stale-global-session regression also failed before the final registry hardening:

```text
begin_task_step_execution accepted a retained registry _session_key when the
per-call ToolExecutionContext omitted it.
```

### GREEN

Final review-focused repair suite:

```text
78 passed in 2.45s
```

Final required Task 7 suite:

```text
49 passed in 1.68s
```

Both runs were followed by a clean `git diff --check`.

## P4b Contract TDD Evidence

### RED

Before the observe allowlist change, the required focused command failed with
the expected missing shell lifecycle field:

```text
tests/test_observe_writer.py::test_observe_slim_trace_preserves_shell_sandbox_lifecycle_without_raw_command
KeyError: 'command_hash'
```

The first draft also exposed two stale test assumptions against the completed
Task 6 APIs: resource-policy reason placement and treating SQLite files as UTF-8
text. Those assertions were narrowed to the public denial contract and raw DB
bytes before implementation.

### P4b Contract Review RED

The strengthened P4b contract suite failed before the status-command metadata
pass-through update:

```text
tests/test_tool_governance_p4b_contract.py::test_p4b_shell_status_commands_expose_safe_lifecycle_without_private_data
KeyError: 'command_hash'
```

This showed that `/prepare_tool` and `/run_approved_tool` lifecycle metadata
omitted safe shell lifecycle fields even though the managed shell runtime had
recorded them.

### P4b Contract Review GREEN

Required focused verification after the safe lifecycle metadata update:

```text
22 passed in 0.76s
```

Wider related verification:

```text
61 passed in 2.97s
```

The strengthened contract records a real private sandbox artifact pair with
`0600` permissions, verifies the runner received the raw command from the
payload vault, and verifies public executor/status/observe-facing data retains
only safe lifecycle metadata.
