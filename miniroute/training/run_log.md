# MiniRoute V1 Run Log

## Repository Preparation

Generated dataset:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.generate_v1_dataset
```

Output:

```json
{
  "train": 875,
  "valid": 184,
  "test": 191,
  "total": 1250,
  "out_dir": "/home/jjh/git_work/akashic-agent/miniroute/data"
}
```

Validated dataset:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.validate_dataset
```

Output:

```json
{
  "ok": true,
  "total_records": 1250,
  "high_risk_test_count": 30,
  "issues": []
}
```

## MiniMind Training

MiniMind training has not been run yet.
