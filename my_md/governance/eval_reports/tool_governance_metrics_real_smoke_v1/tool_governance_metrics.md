# Tool Governance Metrics v1

This report summarizes tool-governance cost, routing, safety, and audit metrics.

## Summary

- mode: `real_llm`
- gate_pass: `false`
- turns: `3`
- cases: `3`
- max_react_iterations: `12`
- max_real_llm_calls: `36`

## Profile Summary

| profile | turns | pass | warn | fail | avg prompt | avg total | avg react | executed tools | forbidden executed | approval bypass | redaction violations | audit coverage failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_open | 3 | 0 | 0 | 3 | 44035 | 48036.33 | 11 | 60 | 43 | 0 | 0 | 0 |

## Paired Delta

| profile | paired cases | prompt tokens | total tokens | ReAct iterations | executed tools |
| --- | ---: | ---: | ---: | ---: | ---: |
