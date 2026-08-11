# MiniRoute Training Commands

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

V3.1 is a historical small-fix dataset. It preserves V3 split
membership and appends a small targeted delta for the remaining V3_2 test
errors. It is no longer the recommended main route after V4.

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

## 分层路由数据

分层方案仍然只训练 MiniRoute 路由能力，不训练具体工具调用或任务规划。
从 V3.1 数据生成两套保持原 split 的数据：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
  -m miniroute.tools.generate_staged_dataset \
  --source-dir miniroute/data \
  --out-dir miniroute/data \
  --source-prefix route_v3_1
```

输出文件：

```text
route_v3_1_intent_train.jsonl
route_v3_1_intent_valid.jsonl
route_v3_1_intent_test.jsonl
route_v3_1_property_train.jsonl
route_v3_1_property_valid.jsonl
route_v3_1_property_test.jsonl
```

第一阶段训练目标：

```json
{"intent": "file_read", "operation": "read", "request_mode": "single"}
```

第二阶段训练目标：

```json
{
  "need_memory": false,
  "tool_scope": ["file_read_tools"],
  "risk_level": "read_only"
}
```

`tool_scope` 可以是多个能力域。具体工具匹配、复合任务拆分和逐步授权仍由 MnemoAgent 完成。

## V4 Dataset

V4 是当前推荐新主线。它不训练五字段输出，只训练三字段场景识别：

```json
{"scene": "task", "operation": "plan", "request_mode": "single"}
```

Generate V4:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.generate_v4_dataset
```

Validate V4:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.validate_dataset --schema v4
```

Upload these files to the MiniMind server:

```text
miniroute/data/route_v4_train.jsonl
miniroute/data/route_v4_valid.jsonl
miniroute/data/route_v4_test.jsonl
```

Cloud MiniMind training:

```bash
cd /home/jjh/git_work/minimind/trainer

python train_lora.py \
  --data_path ../dataset/route_v4_train.jsonl \
  --from_weight full_sft \
  --lora_name lora_route_v4_scene \
  --epochs 3 \
  --batch_size 16 \
  --max_seq_len 1024 \
  --route_mode
```

V4 不能直接使用旧 `eval_route.py` 的五字段评测逻辑。本仓库提供了新的脚本：

```text
miniroute/evaluation/eval_route_v4.py
```

该脚本只校验：

```python
FIELDS = ["scene", "operation", "request_mode"]
```

并使用 V4 枚举：

```python
VALID_SCENES = {
  "chat", "memory", "profile", "task", "file", "status", "content", "action", "unknown"
}
VALID_OPERATIONS = {
  "answer", "query", "update", "plan", "read", "save", "execute", "unknown"
}
VALID_REQUEST_MODES = {"single", "compound"}
```

Evaluate train:

```bash
cd /home/jjh/git_work/minimind

python eval_route_v4.py \
  --data_path dataset/route_v4_train.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v4_scene \
  --device cuda \
  --max_new_tokens 60 \
  --errors_path result/route_v4_train_errors.jsonl
```

Evaluate valid:

```bash
python eval_route_v4.py \
  --data_path dataset/route_v4_valid.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v4_scene \
  --device cuda \
  --max_new_tokens 60 \
  --errors_path result/route_v4_valid_errors.jsonl
```

Evaluate test after the route is stable:

```bash
python eval_route_v4.py \
  --data_path dataset/route_v4_test.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v4_scene \
  --device cuda \
  --max_new_tokens 60 \
  --errors_path result/route_v4_test_errors.jsonl
```

V4 first acceptance gates:

```text
strict_json >= 99%
schema_valid >= 99%
scene accuracy >= 90%
exact_match >= 88%
chat -> action dangerous confusion = 0
unknown -> action dangerous confusion <= 2%
```

## V4.1 Dataset

V4.1 is the recommended next training dataset after the first V4 run. It keeps
the same three-field protocol and fixes the V4 `request_mode` labeling problem.

Generate V4.1:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.generate_v4_1_dataset
```

Validate V4.1:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.validate_dataset --schema v4 --train miniroute/data/route_v4_1_train.jsonl --valid miniroute/data/route_v4_1_valid.jsonl --test miniroute/data/route_v4_1_test.jsonl
```

Upload these files to the MiniMind server:

```text
miniroute/data/route_v4_1_train.jsonl
miniroute/data/route_v4_1_valid.jsonl
miniroute/data/route_v4_1_test.jsonl
```

Cloud MiniMind training:

```bash
cd /home/jjh/git_work/minimind/trainer

python train_lora.py \
  --data_path ../dataset/route_v4_1_train.jsonl \
  --from_weight full_sft \
  --lora_name lora_route_v4_1 \
  --epochs 3 \
  --batch_size 16 \
  --max_seq_len 1024 \
  --route_mode
```

Evaluate train:

```bash
cd /home/jjh/git_work/minimind

python eval_route_v4.py \
  --data_path dataset/route_v4_1_train.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v4_1 \
  --device cuda \
  --max_new_tokens 60 \
  --errors_path result/route_v4_1_train_errors.jsonl
```

Evaluate valid:

```bash
python eval_route_v4.py \
  --data_path dataset/route_v4_1_valid.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v4_1 \
  --device cuda \
  --max_new_tokens 60 \
  --errors_path result/route_v4_1_valid_errors.jsonl
```

Evaluate test after train and valid are stable:

```bash
python eval_route_v4.py \
  --data_path dataset/route_v4_1_test.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v4_1 \
  --device cuda \
  --max_new_tokens 60 \
  --errors_path result/route_v4_1_test_errors.jsonl
```

V4.1 acceptance gates:

```text
strict_json >= 99%
schema_valid >= 99%
scene accuracy >= 94%
operation accuracy >= 94%
request_mode accuracy > 90%
compound recall > 85%
request_mode-only errors < 8% of train
chat -> action dangerous confusion = 0
unknown -> action dangerous confusion = 0
content -> action dangerous confusion < 21 train cases
```

## V4.2 Dataset

V4.2 is the recommended next dataset after V4.1. It keeps the same V4
three-field protocol and fixes the V4.1 split distribution shift by sharing
template families across train/valid/test while holding out sentence variants.

Generate V4.2:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.generate_v4_2_dataset
```

Validate V4.2:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.validate_dataset --schema v4 --train miniroute/data/route_v4_2_train.jsonl --valid miniroute/data/route_v4_2_valid.jsonl --test miniroute/data/route_v4_2_test.jsonl
```

Upload these files to the MiniMind server:

```text
miniroute/data/route_v4_2_train.jsonl
miniroute/data/route_v4_2_valid.jsonl
miniroute/data/route_v4_2_test.jsonl
```

Cloud MiniMind training:

```bash
cd /home/jjh/git_work/minimind/trainer

python train_lora.py \
  --data_path ../dataset/route_v4_2_train.jsonl \
  --from_weight full_sft \
  --lora_name lora_route_v4_2 \
  --epochs 3 \
  --batch_size 16 \
  --max_seq_len 1024 \
  --route_mode
```

Evaluate train:

```bash
cd /home/jjh/git_work/minimind

python eval_route_v4.py \
  --data_path dataset/route_v4_2_train.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v4_2 \
  --device cuda \
  --max_new_tokens 60 \
  --errors_path result/route_v4_2_train_errors.jsonl
```

Evaluate valid:

```bash
python eval_route_v4.py \
  --data_path dataset/route_v4_2_valid.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v4_2 \
  --device cuda \
  --max_new_tokens 60 \
  --errors_path result/route_v4_2_valid_errors.jsonl
```

Evaluate test after train and valid are stable:

```bash
python eval_route_v4.py \
  --data_path dataset/route_v4_2_test.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v4_2 \
  --device cuda \
  --max_new_tokens 60 \
  --errors_path result/route_v4_2_test_errors.jsonl
```

V4.2 acceptance gates:

```text
train exact >= 95%
valid exact >= 85%
test exact >= 85%
valid/test scene >= 90%
valid/test operation >= 90%
valid/test request_mode >= 90%
file_to_action <= 3 on valid/test
unknown_to_action <= 2 on valid/test
```
