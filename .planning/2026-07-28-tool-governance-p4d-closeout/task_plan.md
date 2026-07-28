# Task Plan: Tool Governance P4d Closeout

## Goal

Complete a P4d operational/documentation closeout for the current tool governance stack without opening new execution capabilities.

## Current Phase

Complete

## Scope

In scope:

- Record the current tool governance flow in durable docs.
- Record the current hook boundary after disabling `shell_restore`.
- Produce a concise user/operator manual for approvals, existing approved file side-effect rollback, shell sandbox limits, and audit.
- Run focused smoke/regression commands that prove the documented boundaries.
- Record final P4d conclusions and next-session handoff.

Out of scope:

- No destructive execution.
- No TaskExecution shell resume.
- No shell rollback.
- No network-enabled shell sandbox.
- No external API replay.
- No new `move_to_trash` / `managed_delete` implementation in this plan.

## Phases

### Phase 1: Baseline And Plan Context

- [x] Confirm branch and latest committed shell_restore-disable baseline.
- [x] Read existing P4c/current-state governance records.
- [x] Create isolated P4d planning files under `.planning/2026-07-28-tool-governance-p4d-closeout/`.
- [x] Review this plan with the review skill.
- [x] Revise the plan to pin smoke commands, output files, and negative capability boundaries.
- [x] Verify branch name, `HEAD`, and dirty state before executing Phase 2.
- **Status:** complete

### Phase 2: Documentation Closeout

- [x] Create `my_md/governance/10-tool-governance-operator-manual.md`.
- [x] Ensure manual covers direct allow, defer/approval, deny, existing approved file side-effect rollback only, shell sandbox limits, audit, and hook boundaries.
- [x] Draft docs before smoke, then reconcile them in Phase 4 with the actual smoke results.
- [x] Update `my_md/governance/README.md` to link the operator manual.
- [x] Update `09-tool-governance-current-state.md` only if current records are missing smoke outcomes or handoff details.
- **Status:** complete

### Phase 3: Focused Smoke Verification

- [x] Run hook/resource/policy regression:
  `PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser --with pyyaml --with html2text --with lxml pytest tests/test_plugin_manager.py tests/test_shell_rm_hook.py tests/test_shell_safety_plugin.py tests/test_tool_loop_guard.py tests/test_resource_policy.py tests/test_tool_invocation_policy_gate.py -q -p no:cacheprovider`
  Expected: pass.
- [x] Run file approval/rollback smoke:
  `PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser --with pyyaml --with html2text --with lxml pytest tests/test_status_commands_approved_side_effects.py tests/test_approved_side_effect_runtime.py -q -p no:cacheprovider`
  Expected: pass.
- [x] Run shell sandbox governance smoke:
  `PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser --with pyyaml --with html2text --with lxml pytest tests/test_approved_shell_side_effect_runtime.py tests/test_tool_governance_p4b_contract.py -q -p no:cacheprovider`
  Expected: pass. These tests must not perform real host shell side effects, network access, TaskExecution shell resume, or external replay; they only validate approval-to-policy/sandbox decision contracts with bounded runners and fail-closed cases.
- [x] Run audit ledger smoke:
  `PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio --with json-repair --with docstring-parser --with pyyaml --with html2text --with lxml pytest tests/test_tool_audit_ledger.py tests/test_status_commands_approved_side_effects.py -q -p no:cacheprovider`
  Expected: pass.
- [x] Record exact commands and results in `progress.md`.
- **Status:** complete

### Phase 4: Findings And Boundary Record

- [x] Record final P4d conclusions in `findings.md`.
- [x] Record remaining non-open capabilities and recommended next step.
- [x] Reconcile `10-tool-governance-operator-manual.md` and `09-tool-governance-current-state.md` with actual smoke results.
- [x] Ensure docs do not imply `shell_restore` rewrite, destructive execution, shell rollback, network shell sandbox, TaskExecution shell resume, or external API replay are available.
- **Status:** complete

### Phase 5: Final Verification And Handoff

- [x] Run `git diff --check`.
- [x] Run targeted compile/test verification for changed documentation-adjacent files and governance tests.
- [x] Run documentation boundary search:
  `rg -n "shell_restore.*rewrite|rm -> mv|shell rollback.*available|network-enabled shell sandbox.*available|destructive execution.*available" my_md/governance plugins/shell_restore tests -S`
  Expected: no active-availability claims; historical/negative mentions are acceptable only when explicitly marked disabled/not available.
- [x] Summarize changed files, verification evidence, skipped tests if any, and unresolved risks in `progress.md`.
- [x] Leave branch ready for commit/PR decision.
- **Status:** complete

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Keep P4d as documentation/smoke closeout | P4c already delivers the core safety stack; expanding execution capabilities would raise risk without a product requirement. |
| Do not reopen destructive shell semantics | Destructive commands remain hard-denied until a separately designed, previewable, recoverable managed tool exists. |
| Treat `shell_restore` as legacy disabled | Pre-hook semantic rewrite can hide original destructive intent from later policy. |
| Prefer existing tests for smoke | The goal is to verify current behavior without building a new execution capability. |
| Shell sandbox smoke validates governance, not live container execution | P4d must avoid environment-dependent Docker/Podman live execution and must not create host shell side effects. |
| Rollback wording means file side-effect rollback only | Shell rollback and destructive undo remain out of scope and unavailable. |

## Key Questions

1. Do the docs clearly explain which tool calls are allow/defer/deny?
2. Do the docs clearly explain which approved side effects support rollback?
3. Do the smoke commands prove `rm` is denied and `shell_restore` no longer registers a hook?
4. Do the smoke commands prove file rollback and shell sandbox governance boundaries without opening new capabilities?

## Errors Encountered

| Error | Attempt | Resolution |
|-------|---------|------------|
| Review subagent could not see untracked `.planning` files | 1 | Re-ran review with the plan content embedded directly in the prompt. |

## Notes

- Update phase status as work progresses.
- Log every smoke command and result in `progress.md`.
- Keep all new records free of raw command/output secrets.
