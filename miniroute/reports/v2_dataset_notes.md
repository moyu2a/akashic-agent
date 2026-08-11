# MiniRoute V2 Dataset Notes

## Background

MiniMind route V1 training learned strict JSON output but did not learn stable
routing semantics. The upstream handoff showed low field accuracy on both train
and valid sets, which indicates a data/schema problem rather than only a
training-parameter problem.

## V2 Fixes

- Unified memory/tool semantics:
  - `memory_query` now uses `need_memory=true`, `need_tools=true`, `tool_scope=["memory_tools"]`.
  - `profile_update` now uses `need_memory=true`, `need_tools=true`, `tool_scope=["memory_tools"]`.
- Added explicit label enumeration to every user prompt.
- Added `unknown_tools` to distinguish "needs a tool but no known domain matches" from `none`.
- Added hard-negative `chat` samples containing words such as "记", "保存", "工具", and "偏好".
- Added paired boundary samples for memory query vs profile update, file read vs high-risk execution, and explain-command vs execute-command.
- Replaced the narrow numbered V1 style with more natural, short, long, and boundary-style expressions.
- Shuffled V2 train/valid/test outputs with deterministic seed `20260805`.
- Kept V1 files intact and wrote V2 files under new names.

## Dataset Files

| split | file | records |
| --- | --- | ---: |
| train | `miniroute/data/route_v2_train.jsonl` | 1061 |
| valid | `miniroute/data/route_v2_valid.jsonl` | 227 |
| test | `miniroute/data/route_v2_test.jsonl` | 232 |
| total |  | 1520 |

High-risk records in V2 test set: `35`.

## Validation

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.validate_dataset --train miniroute/data/route_v2_train.jsonl --valid miniroute/data/route_v2_valid.jsonl --test miniroute/data/route_v2_test.jsonl
```

Result:

```json
{
  "ok": true,
  "total_records": 1520,
  "high_risk_test_count": 35,
  "issues": []
}
```

## Training Handoff

Train a new MiniMind adapter as `lora_route_v2`.

Use:

- train: `miniroute/data/route_v2_train.jsonl`
- valid: `miniroute/data/route_v2_valid.jsonl`
- test: `miniroute/data/route_v2_test.jsonl`

Do not mix V1 and V2 results in the same report. V1 proves format learning; V2
is intended to test routing semantics after fixing label and prompt quality.

