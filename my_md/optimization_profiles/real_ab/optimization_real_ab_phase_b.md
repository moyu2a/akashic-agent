# Optimization Real LLM Gated A/B

本报告使用真实 LLM usage 字段记录 token 与时延；prompt/reply 仅保存脱敏预览。

## Summary

- gate_pass: `true`
- turns: `30`
- profiles: `baseline, combined_p1`
- run_ids: `realab-20260804T135350498939Z`

## Profile Summary

| profile | turns | pass | warn | fail | missing/zero usage | unexpected fast path | expected tool missing | denied tools | unregistered tools | forbidden text | tool errors | avg prompt | avg total | avg turn |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 15 | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 27739.1 | 28263.5 | 8300.7ms |
| combined_p1 | 15 | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 24820.7 | 25234.1 | 6917.3ms |

## Paired Delta

| profile | paired cases | total token delta | turn latency delta |
| --- | ---: | ---: | ---: |
| combined_p1 | 15 | -10.72% | -16.67% |
