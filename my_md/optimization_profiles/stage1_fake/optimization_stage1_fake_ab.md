# Optimization Profile Stage 1 Fake Run

本报告用于验证阶段一混合任务 A/B 的 case、profile、分组和报告链路，不代表真实 token/时延收益。

## Summary

- mode: `fake`
- real_llm: `false`
- profiles: `baseline, simple_fast_path`
- cases: `17`
- turns: `34`

## Profile Summary

| profile | cases | pass | warn | fail | fast hits | tool errors | avg prompt | avg total | avg turn |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 17 | 17 | 0 | 0 | 0 | 0 | 20607.5 | 20703.5 | 3303.6ms |
| simple_fast_path | 17 | 17 | 0 | 0 | 4 | 0 | 18496.4 | 18581.1 | 3000.5ms |

## Category Summary

| category | turns | pass | warn | fail | fast hits | tool errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| simple_no_tool | 10 | 10 | 0 | 0 | 4 | 0 |
| tool_task | 10 | 10 | 0 | 0 | 0 | 0 |
| memory_task | 10 | 10 | 0 | 0 | 0 | 0 |
| proactive_task | 4 | 4 | 0 | 0 | 0 | 0 |
