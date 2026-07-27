# Task 7 Report: Observe Slim Trace and P4b Contract

## Implementation

- Extended observe approved-side-effect lifecycle slimming to preserve shell sandbox metadata via an explicit allowlist: command hash, sandbox backend/image, network and mount modes, timeout, exit code, stdout/stderr hashes, byte counts, truncation flags, and duration.
- Added P4b contract tests covering managed shell runtime boundaries: direct approved shell does not reach host invoker, destructive trusted shell is denied before managed-runtime routing, sandbox unavailable fails closed, raw command stays out of public executor/status/observe/DB surfaces, and raw command remains only in the private payload vault.
- Strengthened sandbox test double to record the in-memory command passed to the runner and to write real fake stdout/stderr artifacts with `0600` permissions.
- Added status-command coverage for actual `/prepare_tool` and `/run_approved_tool` shell replies and extra metadata, including safe shell lifecycle fields and redaction of raw command, payload paths, artifact names/paths, and stdout/stderr text.
- Scoped status-command shell lifecycle metadata to shell side effects so P4a file lifecycle metadata is not expanded with empty shell-only fields.

## TDD Evidence

### RED

- Initial observe/contract tests failed before the observe allowlist included shell sandbox fields.
- Review-fix contract assertions initially exposed weak tests: the fake runner did not record the command, no artifact files were written, status-command shell lifecycle metadata did not expose the safe shell fields, and destructive trusted-shell denial metadata was not fully checked.

### GREEN

Required Task 7 tests:

```text
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_tool_governance_p4b_contract.py tests/test_observe_writer.py -q -p no:cacheprovider
22 passed
```

Wider related suite after review fixes:

```text
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_tool_executor_approval_workflow.py tests/test_status_commands_approved_side_effects.py tests/test_approved_shell_side_effect_runtime.py tests/test_tool_governance_p4b_contract.py tests/test_observe_writer.py -q -p no:cacheprovider
61 passed
```

Controller verification after cleanup:

```text
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_tool_governance_p4b_contract.py tests/test_observe_writer.py tests/test_status_commands_approved_side_effects.py -q -p no:cacheprovider
29 passed in 1.41s
```

`git diff --check` passed.

## Concerns

None.

## Re-review Corrective Evidence

### RED

Focused re-review coverage before the production correction:

```text
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_tool_governance_p4b_contract.py tests/test_shell_sandbox_runner.py -q -p no:cacheprovider
1 failed, 19 passed in 0.55s
```

`test_p4b_file_lifecycle_event_excludes_shell_only_metadata` failed because a
`write_file` lifecycle event contained `sandbox_backend`. The new real sandbox
runner artifact test passed, confirming that the existing `_write_private_file()`
implementation produces `0600` stdout/stderr artifacts with result hashes and
byte counts that match the files.

### GREEN

Required re-review suite after scoping `sandbox_backend` to shell events:

```text
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_tool_governance_p4b_contract.py tests/test_observe_writer.py tests/test_status_commands_approved_side_effects.py tests/test_shell_sandbox_runner.py -q -p no:cacheprovider
44 passed in 1.45s
```

`git diff --check` passed.
