# MiniRoute V3.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a V3.1 MiniRoute dataset that preserves the frozen `lora_route_v3_2` baseline and adds targeted small-fix boundary samples for the remaining test errors.

**Architecture:** Keep V3 as immutable evidence and create V3.1 as a separate dataset version. Reuse the existing MiniRoute schema and validator, but preserve V3 split membership for baseline comparability: V3 train/valid/test rows stay in their original split, and only V3.1 delta rows are split deterministically and appended. Do not change model output fields or remove `tool_scope`.

**Tech Stack:** Python, JSONL, MiniMind `conversations` SFT format, pytest, existing `miniroute.v1_schema` route label types.

## Global Constraints

- Do not overwrite `route_v3_train.jsonl`, `route_v3_valid.jsonl`, or `route_v3_test.jsonl`.
- Do not change the five-field output schema: `intent`, `need_memory`, `need_tools`, `tool_scope`, `risk_level`.
- Do not remove `tool_scope`; V3_2 test has reached `78.67%`, so V3.1 should be a targeted data fix.
- Freeze `lora_route_v3_2` as the comparison baseline: train `78.37%`, valid `81.69%`, test `78.67%`, test schema valid `98.61%`.
- V3.1 must add only targeted hard negative / boundary samples, not broad same-template bulk expansion.
- V3.1 files must be named `route_v3_1_train.jsonl`, `route_v3_1_valid.jsonl`, and `route_v3_1_test.jsonl`.
- V3.1 must preserve V3 split membership. Existing `route_v3_train/valid/test` rows cannot move between splits.
- V3.1 must include a bridge evaluation on frozen `route_v3_test.jsonl` in addition to `route_v3_1_test.jsonl`.
- V3.1 added records must be small-fix deltas: cap each `v3_1:` source at `80` records and cap total V3.1 additions at `360` records.
- V3.1 model acceptance target: train `>82%`, valid `>83%`, test `>82%`, schema bad on test `0-1` items, and no regression on frozen `route_v3_test.jsonl` compared with V3_2 `78.67%`.

---

## File Structure

- Create `miniroute/tools/generate_v3_1_dataset.py`: builds V3.1 by reading frozen V3 split files and appending targeted V3.1 records.
- Create `tests/test_miniroute_v3_1.py`: verifies V3.1 sources, labels, generated splits, and validator acceptance.
- Modify `miniroute/data/README.md`: document V3.1 output files and high-risk test count after generation.
- Modify `miniroute/training/train_commands.md`: add V3.1 generation, validation, cloud training, and eval commands.
- Modify `miniroute/my_md/README.md`, `miniroute/my_md/minimind_training_handoff.md`, and `miniroute/my_md/route_experiment_plan.md`: update current next step and baseline comparison.
- Create `miniroute/reports/v3_1_dataset_notes.md`: record modification method, data size, test method, expected training comparison, and rollback/decision criteria.

---

### Task 1: Freeze V3_2 Baseline In Working Docs

**Files:**
- Modify: `miniroute/my_md/README.md`
- Modify: `miniroute/my_md/minimind_training_handoff.md`
- Modify: `miniroute/my_md/route_experiment_plan.md`
- Create: `miniroute/reports/v3_1_dataset_notes.md`

**Interfaces:**
- Consumes: Existing `route_eval_v3_2_test.md` results.
- Produces: A clear V3_2 baseline that V3.1 tests and docs can reference.

- [ ] **Step 1: Add baseline section to V3.1 dataset notes**

Create `miniroute/reports/v3_1_dataset_notes.md` with:

```markdown
# MiniRoute V3.1 数据说明

## Baseline

V3.1 以 `lora_route_v3_2` 作为冻结 baseline。

| 数据集 | V3_2 完全匹配 | 错误率 | Schema 合法 |
| --- | ---: | ---: | ---: |
| train | 78.37% | 21.63% | 99.16% |
| valid | 81.69% | 18.31% | 99.44% |
| test | 78.67% | 21.33% | 98.61% |

V3.1 的目标不是重做任务，而是在保留五字段 schema 的基础上，减少 test 中剩余的边界错误。

## Model Acceptance Targets

| 数据集 | V3_2 baseline | V3.1 目标 |
| --- | ---: | ---: |
| train | 78.37% | > 82% |
| valid | 81.69% | > 83% |
| test | 78.67% | > 82% |

额外目标：

- test schema bad 从 `5` 条降到 `0-1` 条。
- `trace` 不再生成非法 intent。
- `lora_route_v3_1` 在冻结 `route_v3_test.jsonl` 上不低于 V3_2 的 `78.67%`。
```

- [ ] **Step 2: Update current-state docs**

Update the three working docs to state:

```text
V3_2 已冻结为阶段性 baseline。
下一步生成 V3.1 小修数据。
V3.1 不覆盖 V3，不移除 tool_scope。
```

- [ ] **Step 3: Verify documentation references**

Run:

```bash
rg -n "V3_2|V3.1|route_v3_1|78.67|tool_scope" miniroute/my_md miniroute/reports
```

Expected: the baseline and V3.1 next step are discoverable from README, experiment plan, handoff, and V3.1 notes.

---

### Task 2: Add V3.1 Dataset Generator With Targeted Boundary Records

**Files:**
- Create: `miniroute/tools/generate_v3_1_dataset.py`
- Test: `tests/test_miniroute_v3_1.py`

**Interfaces:**
- Consumes: frozen V3 JSONL files from `miniroute/data/`.
- Produces:
  - `build_v3_1_records() -> list[TrainingRecord]`
  - `build_v3_1_delta_records() -> list[TrainingRecord]`
  - `split_v3_1_records(records: Iterable[TrainingRecord]) -> DatasetSplits`
  - `write_v3_1_dataset_files(out_dir: Path) -> DatasetSplits`

- [ ] **Step 1: Write failing tests for V3.1 sources and labels**

Create `tests/test_miniroute_v3_1.py` with tests that import:

```python
from miniroute.tools.generate_v3_1_dataset import (
    build_v3_1_records,
    split_v3_1_records,
)
```

Assert the exact set of `v3_1:` source names is:

```python
{
    "v3_1:trace_status_query_schema_fix",
    "v3_1:task_plan_chat_profile_boundary",
    "v3_1:profile_memory_content_boundary",
    "v3_1:file_read_tool_execution_boundary",
    "v3_1:unknown_tools_boundary",
}
```

Assert key labels:

```python
trace/status_query -> status_query + observe_tools + read_only
task plan requests -> task_plan + task_tools + write
ordinary task explanation requests -> chat + none + none
profile update requests -> profile_update + memory_tools + write
memory query requests -> memory_query + memory_tools + read_only
content save requests -> content_save + content_tools + write
file read requests -> file_read + file_read_tools + read_only
dangerous delete/overwrite/install requests -> tool_execution + shell_tools + high_risk
unknown OCR/audio/image/video requests -> tool_execution + unknown_tools + read_only
```

Assert small-fix constraints:

```python
all v3_1 source counts <= 80
total v3_1 delta records <= 360
no duplicate input text inside v3_1 delta records
```

Assert split preservation:

```python
all original route_v3_train rows remain in route_v3_1_train
all original route_v3_valid rows remain in route_v3_1_valid
all original route_v3_test rows remain in route_v3_1_test
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_miniroute_v3_1.py -q -p no:cacheprovider
```

Expected: FAIL with `ModuleNotFoundError: No module named 'miniroute.tools.generate_v3_1_dataset'`.

- [ ] **Step 3: Implement generator**

Create `miniroute/tools/generate_v3_1_dataset.py` by following the V3 generator style, but do not re-split existing V3 records:

```python
from miniroute.v1_schema import parse_training_record
from miniroute.v1_schema import ROUTE_PROMPT_V2, RouteLabel, TrainingRecord
```

Implementation requirements:

- Read frozen split files from `miniroute/data/route_v3_train.jsonl`, `route_v3_valid.jsonl`, and `route_v3_test.jsonl`.
- Convert frozen JSONL rows back to `TrainingRecord` with `parse_training_record`.
- Append targeted records for:
  - trace/status_query schema fix
  - task_plan/chat/profile_update
  - profile_update/memory_query/content_save
  - file_read/tool_execution
  - unknown_tools/file_read/content_save
- Use `SHUFFLE_SEED = 20260805`.
- Split only V3.1 delta records by intent with deterministic seed strings containing `v3_1`.
- Append delta train rows to frozen V3 train, delta valid rows to frozen V3 valid, and delta test rows to frozen V3 test.
- Write files named `route_v3_1_train.jsonl`, `route_v3_1_valid.jsonl`, `route_v3_1_test.jsonl`.
- Print per-source V3.1 delta counts in the JSON summary.

- [ ] **Step 4: Run V3.1 tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_miniroute_v3_1.py -q -p no:cacheprovider
```

Expected: PASS.

---

### Task 3: Generate, Validate, And Document V3.1 Data

**Files:**
- Modify: `miniroute/data/README.md`
- Modify: `miniroute/training/train_commands.md`
- Modify: `miniroute/reports/v3_1_dataset_notes.md`
- Generate: `miniroute/data/route_v3_1_train.jsonl`
- Generate: `miniroute/data/route_v3_1_valid.jsonl`
- Generate: `miniroute/data/route_v3_1_test.jsonl`

**Interfaces:**
- Consumes: `write_v3_1_dataset_files(out_dir: Path)`.
- Produces: validated V3.1 JSONL files and updated training commands.

- [ ] **Step 1: Generate V3.1 files**

Run:

```bash
.venv/bin/python -m miniroute.tools.generate_v3_1_dataset
```

Expected: JSON summary containing `train`, `valid`, `test`, `total`, `shuffle_seed`, and `out_dir`.

- [ ] **Step 2: Validate V3.1 files**

Run:

```bash
.venv/bin/python -m miniroute.tools.validate_dataset \
  --train miniroute/data/route_v3_1_train.jsonl \
  --valid miniroute/data/route_v3_1_valid.jsonl \
  --test miniroute/data/route_v3_1_test.jsonl
```

Expected: `ok=true`, `issues=[]`, and `high_risk_test_count >= 30`.

- [ ] **Step 3: Prove V3 files are unchanged**

Run:

```bash
git diff -- miniroute/data/route_v3_train.jsonl miniroute/data/route_v3_valid.jsonl miniroute/data/route_v3_test.jsonl
```

Expected: no diff.

- [ ] **Step 4: Document generated sizes and source counts**

Update `miniroute/data/README.md` and `miniroute/reports/v3_1_dataset_notes.md` with the exact generated counts, high-risk test count, and per-source `v3_1:` delta counts.

- [ ] **Step 5: Add MiniMind commands**

Update `miniroute/training/train_commands.md` with:

```bash
python train_lora.py \
  --data_path ../dataset/route_v3_1_train.jsonl \
  --from_weight full_sft \
  --lora_name lora_route_v3_1 \
  --epochs 3 \
  --batch_size 16 \
  --max_seq_len 1024 \
  --route_mode
```

Add train, valid, and test eval commands using `lora_route_v3_1` and `route_v3_1_*.jsonl`.

Add bridge eval command using frozen V3 test:

```bash
python eval_route.py \
  --data_path dataset/route_v3_test.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v3_1 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path result/route_v3_1_bridge_v3_test_errors.jsonl
```

---

### Task 4: Verification And Handoff

**Files:**
- Test: `tests/test_miniroute_v2.py`
- Test: `tests/test_miniroute_v3.py`
- Test: `tests/test_miniroute_v3_1.py`
- Modify: `miniroute/my_md/minimind_training_handoff.md`

**Interfaces:**
- Consumes: generated V3.1 JSONL files and docs.
- Produces: a clean local verification record and clear cloud training handoff.

- [ ] **Step 1: Run full MiniRoute tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_miniroute_v2.py tests/test_miniroute_v3.py tests/test_miniroute_v3_1.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 2: Compile MiniRoute package**

Run:

```bash
.venv/bin/python -m compileall miniroute
```

Expected: command exits `0`.

- [ ] **Step 3: Validate V3.1 data one more time**

Run:

```bash
.venv/bin/python -m miniroute.tools.validate_dataset \
  --train miniroute/data/route_v3_1_train.jsonl \
  --valid miniroute/data/route_v3_1_valid.jsonl \
  --test miniroute/data/route_v3_1_test.jsonl
```

Expected: `ok=true`.

- [ ] **Step 4: Update handoff**

Update `miniroute/my_md/minimind_training_handoff.md` so the current recommended data is V3.1 and the current comparison baseline is:

```text
lora_route_v3_2 test exact: 284/361 = 78.67%
```

Final handoff should tell the cloud runner to train `lora_route_v3_1` and compare train/valid/test against V3_2.

- [ ] **Step 5: Add cloud evaluation acceptance gates**

Update handoff and V3.1 notes to require these reported results before accepting V3.1:

```text
route_v3_1_train exact > 82%
route_v3_1_valid exact > 83%
route_v3_1_test exact > 82%
route_v3_1_test schema bad <= 1
bridge route_v3_test exact >= 78.67%
trace/status_query schema bad improves from V3_2 test 5 items to 0-1 items
```

---

## Acceptance Criteria

- `route_v3_1_train.jsonl`, `route_v3_1_valid.jsonl`, and `route_v3_1_test.jsonl` exist and do not overwrite V3.
- V3.1 local validation passes with no issues.
- V3 files have no git diff after V3.1 generation.
- V3.1 delta records are capped at `<=360`, each `v3_1:` source is `<=80`, and delta input texts have no duplicates.
- Tests cover V3.1 source names, labels, split generation, and validator acceptance.
- Tests cover contrast labels: `chat`, `memory_query`, `content_save`, `tool_execution + shell_tools + high_risk`, and `tool_execution + unknown_tools + read_only`.
- Docs state that `lora_route_v3_2` is frozen as baseline.
- Docs state that V3.1 keeps five fields and does not remove `tool_scope`.
- MiniMind handoff includes exact V3.1 training and evaluation commands.
- MiniMind handoff includes bridge evaluation on frozen `route_v3_test.jsonl`.
- V3.1 is accepted only if cloud eval exceeds the documented model acceptance gates.
