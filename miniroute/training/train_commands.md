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

## V2 Dataset

V2 fixes V1 label contradictions and prompt underspecification. For the next
MiniMind run, train a separate adapter such as `lora_route_v2` with:

- train: `miniroute/data/route_v2_train.jsonl`
- valid: `miniroute/data/route_v2_valid.jsonl`
- test: `miniroute/data/route_v2_test.jsonl`

Validate V2 before upload:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.validate_dataset --train miniroute/data/route_v2_train.jsonl --valid miniroute/data/route_v2_valid.jsonl --test miniroute/data/route_v2_test.jsonl
```

## V3 Dataset

V3 is the historical dataset after the template-fixed baseline. It keeps
the V2 schema and adds hard negatives for:

- `status_query/file_read/content_save` being overpredicted as shell execution.
- `chat` being confused with memory/profile updates.
- `profile_update`, `memory_query`, and `content_save` boundary errors.
- `unknown_tools` being confused with `shell_tools`.

Generate V3:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.generate_v3_dataset
```

Validate V3 before upload:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.validate_dataset --train miniroute/data/route_v3_train.jsonl --valid miniroute/data/route_v3_valid.jsonl --test miniroute/data/route_v3_test.jsonl
```

Cloud MiniMind training:

```bash
cd /home/jjh/git_work/minimind/trainer

python train_lora.py \
  --data_path ../dataset/route_v3_train.jsonl \
  --from_weight full_sft \
  --lora_name lora_route_v3_boundary \
  --epochs 3 \
  --batch_size 16 \
  --max_seq_len 1024 \
  --route_mode
```

Evaluate train first:

```bash
cd /home/jjh/git_work/minimind

python eval_route.py \
  --data_path dataset/route_v3_train.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v3_boundary \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path result/route_v3_boundary_train_errors.jsonl
```

Then evaluate valid:

```bash
python eval_route.py \
  --data_path dataset/route_v3_valid.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v3_boundary \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path result/route_v3_boundary_valid_errors.jsonl
```

## V3.1 Dataset

V3.1 is the current recommended next training dataset. It preserves V3 split
membership and appends a small targeted delta for the remaining V3_2 test
errors.

Generate V3.1:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.generate_v3_1_dataset
```

Validate V3.1 before upload:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.validate_dataset --train miniroute/data/route_v3_1_train.jsonl --valid miniroute/data/route_v3_1_valid.jsonl --test miniroute/data/route_v3_1_test.jsonl
```

Cloud MiniMind training:

```bash
cd /home/jjh/git_work/minimind/trainer

python train_lora.py \
  --data_path ../dataset/route_v3_1_train.jsonl \
  --from_weight full_sft \
  --lora_name lora_route_v3_1 \
  --epochs 3 \
  --batch_size 16 \
  --max_seq_len 1024 \
  --route_mode
```

Evaluate train:

```bash
cd /home/jjh/git_work/minimind

python eval_route.py \
  --data_path dataset/route_v3_1_train.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v3_1 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path result/route_v3_1_train_errors.jsonl
```

Evaluate valid:

```bash
python eval_route.py \
  --data_path dataset/route_v3_1_valid.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v3_1 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path result/route_v3_1_valid_errors.jsonl
```

Evaluate test:

```bash
python eval_route.py \
  --data_path dataset/route_v3_1_test.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v3_1 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path result/route_v3_1_test_errors.jsonl
```

Bridge evaluation on frozen V3 test:

```bash
python eval_route.py \
  --data_path dataset/route_v3_test.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v3_1 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path result/route_v3_1_bridge_v3_test_errors.jsonl
```

V3.1 acceptance gates:

```text
route_v3_1_train exact > 82%
route_v3_1_valid exact > 83%
route_v3_1_test exact > 82%
route_v3_1_test schema bad <= 1
bridge route_v3_test exact >= 78.67%
```
