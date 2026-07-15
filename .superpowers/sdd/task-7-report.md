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
