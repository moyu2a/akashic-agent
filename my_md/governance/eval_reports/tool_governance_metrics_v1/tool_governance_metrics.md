# Tool Governance Metrics v1

This report summarizes tool-governance cost, routing, safety, and audit metrics.

## Summary

- mode: `dry`
- gate_pass: `true`
- turns: `60`
- cases: `20`
- max_react_iterations: `12`
- max_real_llm_calls: `720`

## Profile Summary

| profile | turns | pass | warn | fail | avg prompt | avg total | avg react | executed tools | forbidden executed | approval bypass | redaction violations | audit coverage failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_open | 20 | 20 | 0 | 0 | 39000 | 39420 | 3.75 | 33 | 0 | 0 | 0 | 0 |
| intent_scope_only | 20 | 20 | 0 | 0 | 28080 | 28382 | 2.75 | 24 | 0 | 0 | 0 | 0 |
| full_governance | 20 | 20 | 0 | 0 | 20280 | 20498 | 2.25 | 24 | 0 | 0 | 0 | 0 |

## Paired Delta

| profile | paired cases | prompt tokens | total tokens | ReAct iterations | executed tools |
| --- | ---: | ---: | ---: | ---: | ---: |
| intent_scope_only | 20 | -28.0% | -28.0% | -26.67% | -27.27% |
| full_governance | 20 | -48.0% | -48.0% | -40.0% | -27.27% |
