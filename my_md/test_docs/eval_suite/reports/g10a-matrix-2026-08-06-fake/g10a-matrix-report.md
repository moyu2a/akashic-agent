# G10-A Matrix Report

- Dataset: `g10a-60turn-v1`
- Environment: `fake`
- Provider: `fake`
- Episodes: `60` / `60`
- Security hard gate passed: `True`
- Formal G10-A ready: `False`

## Governance Profiles

| profile | task execution | work tool budget | requires real executor fields |
| --- | --- | --- | --- |
| baseline_open | False | 12 | none |
| budget_limited | True | 2 | none |
| full_governance | True | 3 | tool_scope_enforced, risk_preflight_enabled, approval_required_for_high_risk, path_check_enabled, restricted_execution_enabled |

## Blockers

- environment_kind=fake is structural smoke, not real LLM evidence
