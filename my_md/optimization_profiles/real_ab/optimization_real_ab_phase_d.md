# Optimization Real LLM Gated A/B

本报告使用真实 LLM usage 字段记录 token 与时延；prompt/reply 仅保存脱敏预览。

## Summary

- gate_pass: `true`
- turns: `6`
- profiles: `baseline, tool_result_limit`
- run_ids: `realab-20260804T140053603295Z`

## Profile Summary

| profile | turns | pass | warn | fail | missing/zero usage | unexpected fast path | expected tool missing | denied tools | unregistered tools | forbidden text | tool errors | avg prompt | avg total | avg turn |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 40046 | 40641.3 | 10671ms |
| tool_result_limit | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 43868 | 44511 | 10306.7ms |

## Paired Delta

| profile | paired cases | total token delta | turn latency delta |
| --- | ---: | ---: | ---: |
| tool_result_limit | 3 | 9.52% | -3.41% |
