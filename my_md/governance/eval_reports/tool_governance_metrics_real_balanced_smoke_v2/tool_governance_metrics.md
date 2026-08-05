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
| baseline_open | 4 | 2 | 1 | 1 | 22848.5 | 25015.25 | 6.5 | 34 | 8 | 0 | 0 | 0 |
| intent_scope_only | 4 | 3 | 1 | 0 | 20483.5 | 22602.75 | 5.75 | 37 | 0 | 0 | 0 | 0 |
| full_governance | 4 | 4 | 0 | 0 | 11560.5 | 13152.75 | 4.25 | 15 | 0 | 0 | 0 | 0 |

## Paired Delta

| profile | paired cases | prompt tokens | total tokens | ReAct iterations | executed tools |
| --- | ---: | ---: | ---: | ---: | ---: |
| intent_scope_only | 4 | -10.35% | -9.64% | -11.54% | 8.82% |
| full_governance | 4 | -49.4% | -47.42% | -34.62% | -55.88% |
