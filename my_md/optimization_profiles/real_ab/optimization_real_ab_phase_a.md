# Optimization Real LLM Gated A/B

本报告使用真实 LLM usage 字段记录 token 与时延；prompt/reply 仅保存脱敏预览。

## Summary

- gate_pass: `true`
- turns: `30`
- profiles: `baseline, simple_fast_path`
- run_ids: `realab-20260804T134926389453Z`

## Profile Summary

| profile | turns | pass | warn | fail | missing/zero usage | unexpected fast path | expected tool missing | denied tools | unregistered tools | forbidden text | tool errors | avg prompt | avg total | avg turn |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 15 | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 28577.2 | 29136.8 | 7644.3ms |
| simple_fast_path | 15 | 15 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 24726.7 | 25061.3 | 5462.7ms |

## Paired Delta

| profile | paired cases | total token delta | turn latency delta |
| --- | ---: | ---: | ---: |
| simple_fast_path | 15 | -13.99% | -28.54% |
