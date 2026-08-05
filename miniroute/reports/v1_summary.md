# MiniRoute V1 Summary

## Current Status

MiniRoute V1 repository preparation is complete. The current repository contains
the V1 schema, dataset generator, dataset validator, evaluator helpers, generated
JSONL datasets, and initial documentation.

MiniMind cloud training has not been run in this repository environment. Model
quality metrics will be added after the MiniMind SFT or LoRA run finishes on the
GPU server.

## Dataset

| split | records |
| --- | ---: |
| train | 875 |
| valid | 184 |
| test | 191 |
| total | 1250 |

High-risk records in the fixed test set: `30`.

Data format: MiniMind `conversations` JSONL.

## Validation

Dataset validation command:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.validate_dataset
```

Result:

```json
{
  "ok": true,
  "total_records": 1250,
  "high_risk_test_count": 30,
  "issues": []
}
```

## Training Status

Training is pending external MiniMind setup on a GPU server.

V1 training should use:

- Base model: MiniMind pretrained checkpoint.
- Method: SFT or LoRA, with LoRA preferred for first iteration.
- Train data: `miniroute/data/route_train.jsonl`.
- Validation data: `miniroute/data/route_valid.jsonl`.
- Fixed test data: `miniroute/data/route_test.jsonl`.

## Next Step

Run MiniMind SFT or LoRA on the generated dataset, then use the fixed test set to
fill `miniroute/evaluation/eval_report.md` and
`miniroute/reports/error_analysis.md` with model results.
