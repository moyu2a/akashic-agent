# Tool Governance Metrics v1

This report summarizes tool-governance cost, routing, safety, and audit metrics.

## Summary

- mode: `real_llm`
- gate_pass: `false`
- turns: `12`
- cases: `4`
- max_react_iterations: `12`
- max_real_llm_calls: `144`

## Profile Summary

| profile | turns | pass | warn | fail | avg prompt | avg total | avg react | executed tools | forbidden executed | approval bypass | redaction violations | audit coverage failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_open | 4 | 0 | 2 | 2 | 29437.25 | 34511.75 | 7.75 | 48 | 22 | 0 | 0 | 0 |
| intent_scope_only | 4 | 3 | 1 | 0 | 23637.5 | 26077 | 6.5 | 41 | 0 | 0 | 0 | 0 |
| full_governance | 4 | 3 | 1 | 0 | 14549 | 16308.75 | 4.75 | 22 | 0 | 0 | 0 | 0 |

## Paired Delta

| profile | paired cases | prompt tokens | total tokens | ReAct iterations | executed tools |
| --- | ---: | ---: | ---: | ---: | ---: |
| intent_scope_only | 4 | -19.7% | -24.44% | -16.13% | -14.58% |
| full_governance | 4 | -50.58% | -52.74% | -38.71% | -54.17% |
