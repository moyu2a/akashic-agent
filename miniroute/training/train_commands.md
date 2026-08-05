# MiniRoute V1 Training Commands

## Local Repository Commands

Generate the V1 dataset:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.generate_v1_dataset
```

Validate the V1 dataset:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.validate_dataset
```

Run local MiniRoute tests:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_miniroute_v1.py -q -p no:cacheprovider
```

## Cloud MiniMind Training

MiniMind training should be run on the GPU server after the official MiniMind
inference and SFT or LoRA demo works.

Use these repository files as inputs:

- train: `miniroute/data/route_train.jsonl`
- valid: `miniroute/data/route_valid.jsonl`
- test: `miniroute/data/route_test.jsonl`

Each line uses MiniMind `conversations` format:

```json
{"conversations":[{"role":"user","content":"判断用户请求的意图、记忆需求、工具需求、工具范围和风险等级，并只输出 JSON。\n\n用户请求：帮我解释一下这个概念，第1版。"},{"role":"assistant","content":"{\"intent\": \"chat\", \"need_memory\": false, \"need_tools\": false, \"tool_scope\": [\"none\"], \"risk_level\": \"none\"}"}]}
```

Record the exact cloud command, model checkpoint, MiniMind commit, GPU type, and
training output directory in `run_log.md` after training.
