# Task 1 Report: Extend Private Payload Vault to Shell

Date: 2026-07-27
Worktree: `/home/jjh/git_work/akashic-agent/.worktrees/tool-approval-next`

## Scope

Implemented Task 1 for P4b shell payload storage only, limited to:

- `agent/policies/side_effect_payload_vault.py`
- `agent/policies/__init__.py`
- `tests/test_side_effect_payload_vault.py`

No unrelated files were modified.

## TDD Sequence

1. Added a new focused test:
   - `test_payload_vault_stores_exact_shell_arguments_privately`
2. Ran the focused test first and confirmed the required failure:
   - `ValueError: unsupported managed side-effect tool: shell`
3. Implemented the minimal production changes to support private shell payload storage.
4. Re-ran the focused test and confirmed it passed.
5. Ran the full vault test file and confirmed all tests passed.

## Code Changes

### `agent/policies/side_effect_payload_vault.py`

- Added `MANAGED_SHELL_SIDE_EFFECT_TOOLS = frozenset({"shell"})`
- Added `MANAGED_SIDE_EFFECT_TOOLS = MANAGED_FILE_SIDE_EFFECT_TOOLS | MANAGED_SHELL_SIDE_EFFECT_TOOLS`
- Updated `put_payload(...)` to accept any tool in `MANAGED_SIDE_EFFECT_TOOLS`
- Updated `get_payload(...)` to accept any tool in `MANAGED_SIDE_EFFECT_TOOLS`
- Ensured private vault directories are created with mode `0700`
- Kept payload files at mode `0600`

### `agent/policies/__init__.py`

- Exported:
  - `MANAGED_SHELL_SIDE_EFFECT_TOOLS`
  - `MANAGED_SIDE_EFFECT_TOOLS`

### `tests/test_side_effect_payload_vault.py`

- Added the shell payload privacy/storage test from the brief
- Updated the unsupported-tool test to keep validating rejection behavior with an actually unsupported tool (`browser`)

## Verification

Focused red test:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_side_effect_payload_vault.py::test_payload_vault_stores_exact_shell_arguments_privately -q -p no:cacheprovider
```

Observed before implementation:

- `FAILED tests/test_side_effect_payload_vault.py::test_payload_vault_stores_exact_shell_arguments_privately`
- `ValueError: unsupported managed side-effect tool: shell`

Observed after implementation:

- `1 passed in 0.12s`

Full vault test file:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser pytest tests/test_side_effect_payload_vault.py -q -p no:cacheprovider
```

Observed result:

- `4 passed in 0.12s`

## Notes

- The raw shell command remains stored only in the private vault payload file.
- The existing unsupported-tool test needed adjustment because `shell` is now a managed side-effect tool for this task.

## Post-review fix

- Removed the extra `chmod` on the shared `tool_side_effects` parent directory so only the payload subtree is forced private.
- Re-ran the Task 1 focused shell vault test and the full vault test file after the fix:
  - `1 passed in 0.12s`
  - `4 passed in 0.13s`
