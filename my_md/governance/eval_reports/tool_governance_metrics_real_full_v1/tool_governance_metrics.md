# Tool Governance Metrics v1

This report summarizes tool-governance cost, routing, safety, and audit metrics.

## Summary

- mode: `real_llm`
- gate_pass: `false`
- turns: `60`
- cases: `20`
- max_react_iterations: `12`
- max_real_llm_calls: `720`

## Profile Summary

| profile | turns | pass | warn | fail | avg prompt | avg total | avg react | executed tools | forbidden executed | approval bypass | redaction violations | audit coverage failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_open | 20 | 11 | 4 | 5 | 17054.4 | 18909.1 | 5.5 | 128 | 29 | 0 | 0 | 0 |
| intent_scope_only | 20 | 17 | 3 | 0 | 9652.45 | 10960.6 | 4.2 | 92 | 0 | 0 | 0 | 0 |
| full_governance | 20 | 16 | 4 | 0 | 5360.85 | 6259.05 | 2.9 | 44 | 0 | 0 | 1 | 0 |

## Paired Delta

| profile | paired cases | prompt tokens | total tokens | ReAct iterations | executed tools |
| --- | ---: | ---: | ---: | ---: | ---: |
| intent_scope_only | 20 | -43.4% | -42.04% | -23.64% | -28.12% |
| full_governance | 20 | -68.57% | -66.9% | -47.27% | -65.62% |
