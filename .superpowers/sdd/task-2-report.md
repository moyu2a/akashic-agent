# Task 2 Report: Shell Sandbox Preview Planning

Date: 2026-07-27
Base commit before task: `6c2424a`
Worktree: `/home/jjh/git_work/akashic-agent/.worktrees/tool-approval-next`

## Scope Completed

- Added `agent/policies/shell_sandbox_plan.py`
- Exported the new preview types and helpers from `agent/policies/__init__.py`
- Added focused tests in `tests/test_shell_sandbox_plan.py`

## TDD Evidence

### Red

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_shell_sandbox_plan.py -q -p no:cacheprovider
```

Observed failure:

```text
ModuleNotFoundError: No module named 'agent.policies.shell_sandbox_plan'
```

This matched the expected import failure from the task brief.

### Green

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_shell_sandbox_plan.py -q -p no:cacheprovider
```

Observed result:

```text
2 passed in 0.12s
```

## Implementation Notes

- `ShellSandboxPolicy` carries the fixed default sandbox policy values from the brief.
- `ShellSandboxPreview` exposes only hashed and redacted command data through `to_metadata()`.
- `prepare_shell_sandbox_preview(...)`:
  - requires a non-empty shell command
  - creates a unique preview artifact directory
  - caps timeout to the policy maximum
  - records background execution request state without allowing it by default
- No raw shell command is written into preview metadata.
- No command artifact file or `command_ref` field is created.

## Files Changed

- `agent/policies/shell_sandbox_plan.py`
- `agent/policies/__init__.py`
- `tests/test_shell_sandbox_plan.py`

## Concerns

- Verification was intentionally limited to the focused test file required by the task brief.
