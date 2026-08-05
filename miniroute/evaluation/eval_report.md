# MiniRoute V1 Evaluation Report

## Status

No trained MiniMind model has been evaluated yet. This report currently records
the repository-side data validation result that must pass before cloud training.

## Dataset Validation

| metric | value |
| --- | ---: |
| validation passed | true |
| total records | 1250 |
| train records | 875 |
| valid records | 184 |
| test records | 191 |
| high-risk test records | 30 |
| issues | 0 |
| data format | MiniMind `conversations` JSONL |

## Model Metrics

Model metrics will be recorded after the first MiniMind SFT or LoRA run.

Required V1 metrics:

- JSON legality rate.
- intent accuracy.
- need_memory accuracy.
- need_tools accuracy.
- tool_scope accuracy.
- risk_level accuracy.
- high-risk recall.
- forbidden tool mis-open rate.

## V1 Gate

The data gate is passed. The model gate is pending until a trained MiniMind
checkpoint is available.
