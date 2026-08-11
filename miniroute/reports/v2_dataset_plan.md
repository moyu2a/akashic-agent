# MiniRoute V2 Dataset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Subagents are not allowed in this side conversation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a MiniRoute V2 dataset that fixes V1 routing-semantic failures while preserving MiniMind `conversations` JSONL compatibility.

**Architecture:** Keep V1 files as historical artifacts and add V2-specific generation, validation, and reporting. V2 changes the label contract by treating memory as a tool/ability domain, adding `unknown_tools`, using a stronger schema-enumerated prompt, adding boundary/hard-negative samples, and shuffling train/valid/test outputs.

**Tech Stack:** Python 3.12+, stdlib JSON/dataclasses, pytest, existing `miniroute` package.

## Global Constraints

- Keep all MiniRoute files under `miniroute/`.
- Do not remove or rewrite V1 datasets; V2 outputs must use `route_v2_*.jsonl` names.
- Keep MiniMind `conversations` format.
- MiniRoute outputs coarse tool domains, not concrete tool names.
- MiniRoute output is a routing suggestion, not final tool authorization.
- V2 route task must not use reasoning or `<think>` content.

---

## Problem And Solution Record

### V1 Problems

1. Memory labels conflict with tool labels: V1 used `need_tools=false` with `tool_scope=["memory_tools"]`.
2. Prompt does not list valid enum values, so the model can invent schema-external labels.
3. Tool scopes do not have a safe fallback for unknown tool needs, so the model may choose `none`.
4. `chat` boundaries are weak, especially with words like "记", "保存", "工具", "偏好".
5. `memory_query` and `profile_update` boundaries are weak.
6. `file_read` and `tool_execution` boundaries are weak, causing high-risk requests to be predicted as read-only.
7. V1 samples are overly templated with repeated numbered variants.
8. Train/valid/test are grouped by intent instead of shuffled.

### V2 Decisions

1. Treat memory as a tool/ability domain in the route layer:
   - `memory_query`: `need_memory=true`, `need_tools=true`, `tool_scope=["memory_tools"]`, `risk_level="read_only"`.
   - `profile_update`: `need_memory=true`, `need_tools=true`, `tool_scope=["memory_tools"]`, `risk_level="write"`.
2. Use explicit prompt enumeration in every user message:
   - list allowed `intent`, `tool_scope`, and `risk_level` values.
   - state that `tool_scope` is a coarse tool domain and not concrete authorization.
3. Add `unknown_tools` to `tool_scope`:
   - `none` means clearly no tool is needed.
   - `unknown_tools` means a tool seems needed but the request does not match current domains.
4. Add hard negatives and paired boundary samples for `chat`, memory, file read, and high-risk execution.
5. Shuffle generated V2 train/valid/test files with deterministic seed `20260805`.
6. Keep V2 generated outputs separate:
   - `miniroute/data/route_v2_train.jsonl`
   - `miniroute/data/route_v2_valid.jsonl`
   - `miniroute/data/route_v2_test.jsonl`
   - optional debug sorted file may be added only if useful, but main files must be shuffled.

---

## Task 1: V2 Schema And Prompt Contract

**Files:**

- Modify: `miniroute/v1_schema.py`
- Test: `tests/test_miniroute_v2.py`

**Interfaces:**

- Consume: existing `RouteLabel`, `TrainingRecord`, `parse_training_record`.
- Produce:
  - `TOOL_SCOPES` includes `unknown_tools`.
  - `ROUTE_PROMPT_V2: str`.
  - `TrainingRecord.to_training_json()` keeps `conversations` format and can use V2 instruction text.

- [x] Add tests asserting `unknown_tools` is a valid tool scope and `ROUTE_PROMPT_V2` includes enum lists.
- [x] Run `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_miniroute_v2.py -q -p no:cacheprovider` and verify the new tests fail.
- [x] Add `unknown_tools` to `TOOL_SCOPES`.
- [x] Add `ROUTE_PROMPT_V2` with exact allowed enum lists and no `<think>` text.
- [x] Run the same test command and verify it passes.

## Task 2: V2 Dataset Generator

**Files:**

- Create: `miniroute/tools/generate_v2_dataset.py`
- Test: `tests/test_miniroute_v2.py`

**Interfaces:**

- Consume: `RouteLabel`, `TrainingRecord`, `ROUTE_PROMPT_V2`.
- Produce:
  - `build_v2_records() -> list[TrainingRecord]`
  - `split_v2_records(records: Iterable[TrainingRecord]) -> DatasetSplits`
  - `write_v2_dataset_files(out_dir: Path) -> DatasetSplits`

- [x] Add tests asserting V2 records include memory labels with `need_tools=true`.
- [x] Add tests asserting V2 contains `unknown_tools` samples.
- [x] Add tests asserting V2 output order is shuffled and not grouped by intent.
- [x] Run targeted tests and verify they fail because the V2 generator does not exist.
- [x] Implement V2 generator with natural templates, hard negatives, boundary pairs, unknown tool samples, and deterministic shuffle seed `20260805`.
- [x] Run targeted tests and verify they pass.

## Task 3: V2 Validation Support

**Files:**

- Modify: `miniroute/tools/validate_dataset.py`
- Test: `tests/test_miniroute_v2.py`

**Interfaces:**

- Consume: V2 JSONL files in `miniroute/data/`.
- Produce: CLI can validate either V1 defaults or V2 paths via explicit arguments.

- [x] Add a test validating generated V2 train/valid/test files in a temp directory.
- [x] Add checks that no schema-external enum appears.
- [x] Add checks that `need_tools=false` only pairs with `tool_scope=["none"]`.
- [x] Add checks that `unknown_tools` never pairs with `need_tools=false`.
- [x] Run targeted tests and verify failure before implementation.
- [x] Implement validation consistency checks.
- [x] Run targeted tests and verify pass.

## Task 4: Generate V2 Dataset And Docs

**Files:**

- Create: `miniroute/data/route_v2_train.jsonl`
- Create: `miniroute/data/route_v2_valid.jsonl`
- Create: `miniroute/data/route_v2_test.jsonl`
- Create: `miniroute/reports/v2_dataset_notes.md`
- Modify: `miniroute/label_schema.md`
- Modify: `miniroute/training/train_commands.md`

**Interfaces:**

- Consume: V2 generator and validator.
- Produce: generated MiniMind-compatible V2 files and report notes for training handoff.

- [x] Run `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.generate_v2_dataset`.
- [x] Run `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.validate_dataset --train miniroute/data/route_v2_train.jsonl --valid miniroute/data/route_v2_valid.jsonl --test miniroute/data/route_v2_test.jsonl`.
- [x] Update docs to state V2 should train `lora_route_v2`, not overwrite V1 evidence.
- [x] Record counts, decisions, and upstream handoff fixes in `v2_dataset_notes.md`.

## Task 5: Final Verification

**Files:**

- Test: `tests/test_miniroute_v1.py`
- Test: `tests/test_miniroute_v2.py`

**Commands:**

- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_miniroute_v1.py tests/test_miniroute_v2.py -q -p no:cacheprovider`
- [x] `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q miniroute tests/test_miniroute_v1.py tests/test_miniroute_v2.py`
- [x] V2 dataset validation command from Task 4.
- [x] `git status --short miniroute tests/test_miniroute_v1.py tests/test_miniroute_v2.py`

## Execution Review Result

- V2 fixes the V1 memory/tool contradiction by making memory query and profile update enter `memory_tools` with `need_tools=true`.
- V2 prompt enumerates all valid `intent`, `tool_scope`, and `risk_level` values and contains no `<think>` instruction.
- V2 adds `unknown_tools` so unknown tool demand is not mislabeled as `none`.
- V2 includes hard-negative chat samples and boundary samples for memory, file, status, unknown tool, and high-risk execution cases.
- V2 train/valid/test files are deterministic-shuffled instead of grouped by intent.
- V1 files are preserved; V2 files use `route_v2_*.jsonl`.
- Strict consistency validation is gated to V2 file names so V1 historical data remains valid for comparison.

## Final Verification Result

- `tests/test_miniroute_v1.py tests/test_miniroute_v2.py`: `11 passed in 0.20s`.
- `compileall -q miniroute tests/test_miniroute_v1.py tests/test_miniroute_v2.py`: passed.
- V2 validation: `ok=true`, `total_records=1520`, `high_risk_test_count=35`, `issues=[]`.
- V1 validation: `ok=true`, `total_records=1250`, `high_risk_test_count=30`, `issues=[]`.

## Review Checklist

- V2 fixes the memory/tool contradiction.
- V2 prompt enumerates all valid labels.
- V2 adds `unknown_tools` and keeps `none` semantically separate.
- V2 includes boundary/hard-negative samples.
- V2 main dataset files are shuffled.
- V2 keeps V1 files intact.
- No subagents are used in this side conversation.
