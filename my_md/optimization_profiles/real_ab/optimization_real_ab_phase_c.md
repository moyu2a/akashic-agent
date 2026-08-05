# Optimization Real LLM Gated A/B

本报告使用真实 LLM usage 字段记录 token 与时延；prompt/reply 仅保存脱敏预览。

## Summary

- gate_pass: `true`
- turns: `10`
- profiles: `baseline, context20`
- run_ids: `realab-20260804T135823012340Z`

## Profile Summary

| profile | turns | pass | warn | fail | missing/zero usage | unexpected fast path | expected tool missing | denied tools | unregistered tools | forbidden text | tool errors | avg prompt | avg total | avg turn |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 35488.2 | 36236.6 | 11191ms |
| context20 | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 35640.6 | 36397.4 | 11927.6ms |

## Paired Delta

| profile | paired cases | total token delta | turn latency delta |
| --- | ---: | ---: | ---: |
| context20 | 5 | 0.44% | 6.58% |
