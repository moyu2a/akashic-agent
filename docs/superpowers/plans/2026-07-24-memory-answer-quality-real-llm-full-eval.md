# Memory Answer Quality Real LLM Full Eval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the full real-LLM answer/retrieval uplift evaluation and produce reliable tables showing each memory retrieval profile's contribution against the original memory baseline.

**Architecture:** Reuse the existing `scripts/run_memory_comprehensive_online_eval.py` runner and `memory2/eval_comprehensive_online.py` report builder. The run uses real `AgentLoop.process_direct()`, controlled synthetic memory cases, checkpoint/resume, and the answer-quality profile subset only. No production memory DB, observe DB, write governance, or sleep consolidation mutation is involved.

**Tech Stack:** Python, pytest, existing AgentLoop, `memory2.eval_comprehensive_online`, `memory2.eval_quantitative_cases`, JSONL checkpoint, Markdown/JSON reports.

## Global Constraints

- Focus only on the recall and answer uplift table.
- Do not include `chain_write_value` or `chain_sleep_consolidation` in the answer-quality main matrix.
- Use `chain_memory_base` as the original memory baseline.
- Use the full current `comprehensive/all` case pack: `320` unique cases.
- Use these six profiles only: `chain_memory_base,chain_tri_retrieval,chain_graph_retrieval,chain_rerank_injection,chain_version_provenance,chain_all_on`.
- Expected real model call count: `320 * 6 * 1 * 1 = 1920`.
- Interpret `chain_tri_retrieval`, `chain_graph_retrieval`, `chain_rerank_injection`, and `chain_version_provenance` as separate profile evidence-source comparisons, not as true cumulative feature toggles.
- Interpret `chain_all_on` as the current full-chain compatibility/check row. In current code it uses `sleep_consolidation.filtered_active_ids`, so it is not a sleep-free pure answer/retrieval module.
- Always use `--checkpoint-jsonl` and `--resume`.
- Do not print or commit API keys.
- Do not write production memory storage; use isolated `/tmp` workspace paths.
- Do not copy or commit `answer_debug`; it can contain full answer text and injected evidence blocks.
- Do not stage unrelated dirty files, especially `.superpowers/sdd/*.diff`.
- Treat timeout/provider errors as infrastructure failures; rebuild a checkpoint-only report with `--exclude-infra-failures` before interpreting partial data.

---

## File Structure

- Existing runner: `scripts/run_memory_comprehensive_online_eval.py`
  - Responsible for CLI args, provider construction, checkpoint mode, report writing.
- Existing report builder: `memory2/eval_comprehensive_online.py`
  - Responsible for answer-quality uplift rows, chain uplift rows, cost/latency rows, checkpoint loading.
- Existing test data builder: `memory2/eval_quantitative_cases.py`
  - Responsible for `standard` and `comprehensive` case packs.
- Output reports:
  - `/tmp/akashic-memory-answer-quality-real-full-v1/reports/memory_comprehensive_online_eval.json`
  - `/tmp/akashic-memory-answer-quality-real-full-v1/reports/memory_comprehensive_online_eval.md`
  - `/tmp/akashic-memory-answer-quality-real-full-v1/reports/memory_comprehensive_online_eval.checkpoint.jsonl`
- Checkpoint-only rebuilt reports:
  - `/tmp/akashic-memory-answer-quality-real-full-v1/checkpoint-report/memory_comprehensive_online_eval.json`
  - `/tmp/akashic-memory-answer-quality-real-full-v1/checkpoint-report/memory_comprehensive_online_eval.md`
- Documentation to update after execution:
  - `my_md/memory_optimization/README.md`
  - `my_md/memory_optimization/05-memory-target-metric-eval-plan.md`
  - `my_md/memory_optimization/06-memory-320-baseline-plus-count-eval.md`
  - `progress.md`
  - `task_plan.md`

## Task 1: Preflight Real LLM Configuration And Case Matrix

**Files:**
- Read: `scripts/run_memory_comprehensive_online_eval.py`
- Read: `memory2/eval_quantitative_cases.py`
- No code changes.

**Interfaces:**
- Consumes: `build_quantitative_eval_cases(case_pack="comprehensive", case_set="all", limit=0)`
- Produces: confirmed run size and provider availability.

- [ ] **Step 1: Confirm the full case count**

Run:

```bash
.venv/bin/python - <<'PY'
from memory2.eval_quantitative_cases import build_quantitative_eval_cases
cases = build_quantitative_eval_cases(case_pack="comprehensive", case_set="all", limit=0)
print(len(cases))
PY
```

Expected output:

```text
320
```

- [ ] **Step 2: Confirm the real config exists without printing secrets**

Run:

```bash
.venv/bin/python - <<'PY'
from agent.config import load_config
cfg = load_config("/home/jjh/git_work/akashic-agent/config.toml")
print("provider=", cfg.provider)
print("model=", cfg.model)
print("api_key_present=", bool(cfg.api_key))
print("base_url_present=", bool(cfg.base_url))
PY
```

Expected output:

```text
api_key_present= True
```

The exact provider, model, and base URL may vary by local config. Do not print the key itself.

- [ ] **Step 3: Confirm the profile matrix size**

Run:

```bash
.venv/bin/python - <<'PY'
cases = 320
profiles = 6
prompt_variants = 1
repeats = 1
print(cases * profiles * prompt_variants * repeats)
PY
```

Expected output:

```text
1920
```

## Task 2: Run A Small Real-Provider Smoke With The Final Matrix Shape

**Files:**
- Output: `/tmp/akashic-memory-answer-quality-real-smoke-v1/reports/memory_comprehensive_online_eval.json`
- Output: `/tmp/akashic-memory-answer-quality-real-smoke-v1/reports/memory_comprehensive_online_eval.md`
- Output: `/tmp/akashic-memory-answer-quality-real-smoke-v1/reports/memory_comprehensive_online_eval.checkpoint.jsonl`

**Interfaces:**
- Consumes: real LLM provider from `/home/jjh/git_work/akashic-agent/config.toml`
- Produces: proof that the exact six-profile matrix works with real provider before spending the full budget.

- [ ] **Step 1: Run 10-case real smoke**

Run:

```bash
.venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-answer-quality-real-smoke-v1/workspace \
  --out-dir /tmp/akashic-memory-answer-quality-real-smoke-v1/reports \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --case-pack comprehensive \
  --case-set all \
  --limit 10 \
  --profiles chain_memory_base,chain_tri_retrieval,chain_graph_retrieval,chain_rerank_injection,chain_version_provenance,chain_all_on \
  --repeats 1 \
  --prompt-variants baseline \
  --concurrency 2 \
  --timeout-s 120 \
  --checkpoint-jsonl /tmp/akashic-memory-answer-quality-real-smoke-v1/reports/memory_comprehensive_online_eval.checkpoint.jsonl \
  --resume \
  --include-answer-debug \
  --real-memory-workspace /tmp/akashic-memory-answer-quality-real-smoke-v1/empty-real-workspace
```

Expected behavior:

- Exit code `0` if provider calls complete without timeout/provider failure.
- `case_count = 60`.
- `unique_case_count = 10`.
- `profile_count = 6`.
- `real_llm_enabled = True`.
- `answer_quality_partial_matrix = False`.
- `answer_quality_missing_profiles = []`.

- [ ] **Step 2: Inspect smoke metrics without exposing raw prompts**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
p = Path("/tmp/akashic-memory-answer-quality-real-smoke-v1/reports/memory_comprehensive_online_eval.json")
data = json.loads(p.read_text())
keys = [
    "real_llm_enabled",
    "infra_passed",
    "case_count",
    "unique_case_count",
    "profile_count",
    "answer_rule_pass_rate",
    "memory_grounding_pass_rate",
    "forbidden_violation_rate",
    "avg_total_token_count",
    "avg_latency_ms",
    "answer_quality_partial_matrix",
    "answer_quality_missing_profiles",
]
for key in keys:
    print(f"{key}={data['metrics'].get(key)}")
PY
```

Expected output:

```text
real_llm_enabled=True
infra_passed=True
case_count=60
unique_case_count=10
profile_count=6
answer_quality_partial_matrix=False
answer_quality_missing_profiles=[]
```

If `infra_passed=False`, stop before the full run and inspect provider errors/timeouts.

## Task 3: Run The Full Real LLM Answer/Retrieval Uplift Matrix

**Files:**
- Output: `/tmp/akashic-memory-answer-quality-real-full-v1/reports/memory_comprehensive_online_eval.json`
- Output: `/tmp/akashic-memory-answer-quality-real-full-v1/reports/memory_comprehensive_online_eval.md`
- Output: `/tmp/akashic-memory-answer-quality-real-full-v1/reports/memory_comprehensive_online_eval.checkpoint.jsonl`

**Interfaces:**
- Consumes: validated real-provider smoke.
- Produces: complete real LLM matrix for the recall and answer uplift table.

- [ ] **Step 1: Run the full 1920-call matrix**

Run:

```bash
.venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-answer-quality-real-full-v1/workspace \
  --out-dir /tmp/akashic-memory-answer-quality-real-full-v1/reports \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --case-pack comprehensive \
  --case-set all \
  --profiles chain_memory_base,chain_tri_retrieval,chain_graph_retrieval,chain_rerank_injection,chain_version_provenance,chain_all_on \
  --repeats 1 \
  --prompt-variants baseline \
  --concurrency 2 \
  --timeout-s 120 \
  --checkpoint-jsonl /tmp/akashic-memory-answer-quality-real-full-v1/reports/memory_comprehensive_online_eval.checkpoint.jsonl \
  --resume \
  --include-answer-debug \
  --real-memory-workspace /tmp/akashic-memory-answer-quality-real-full-v1/empty-real-workspace
```

Expected behavior:

- `case_count = 1920`.
- `unique_case_count = 320`.
- `profile_count = 6`.
- `prompt_variant_count = 1`.
- `repeat_count = 1`.
- `real_llm_enabled = True`.
- `answer_quality_partial_matrix = False`.
- `answer_quality_missing_profiles = []`.
- Each required profile has exactly `320` valid rows before making full-matrix conclusions.

- [ ] **Step 2: If the run is interrupted, resume with the exact same command**

Run the same command from Step 1 again.

Expected behavior:

- Existing completed rows are skipped from checkpoint.
- No completed call is repeated.
- Final report eventually reaches `case_count = 1920`.

## Task 4: Rebuild A Checkpoint-Only Report For Interpretation

**Files:**
- Read: `/tmp/akashic-memory-answer-quality-real-full-v1/reports/memory_comprehensive_online_eval.checkpoint.jsonl`
- Output: `/tmp/akashic-memory-answer-quality-real-full-v1/checkpoint-report/memory_comprehensive_online_eval.json`
- Output: `/tmp/akashic-memory-answer-quality-real-full-v1/checkpoint-report/memory_comprehensive_online_eval.md`

**Interfaces:**
- Consumes: full or partial checkpoint JSONL.
- Produces: report that can exclude infrastructure failures before analysis.

- [ ] **Step 1: Rebuild from checkpoint excluding infra failures**

Run:

```bash
.venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-answer-quality-real-full-v1/checkpoint-report-workspace \
  --out-dir /tmp/akashic-memory-answer-quality-real-full-v1/checkpoint-report \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --checkpoint-jsonl /tmp/akashic-memory-answer-quality-real-full-v1/reports/memory_comprehensive_online_eval.checkpoint.jsonl \
  --checkpoint-report-only \
  --exclude-infra-failures \
  --real-memory-workspace /tmp/akashic-memory-answer-quality-real-full-v1/empty-real-workspace
```

Expected behavior:

- No new LLM calls are made.
- `checkpoint_report_only = True`.
- `real_llm_enabled = True`.
- `excluded_infra_failure_count = 0` for a clean run, or a positive number if provider errors/timeouts occurred.

## Task 5: Extract The Two Main Result Tables

**Files:**
- Read: `/tmp/akashic-memory-answer-quality-real-full-v1/checkpoint-report/memory_comprehensive_online_eval.json`
- No code changes unless the report schema is missing expected fields.

**Interfaces:**
- Consumes: checkpoint-only JSON report.
- Produces: terminal tables suitable for direct user review. The second table is an ordered profile comparison, not proof of true cumulative feature toggling.

- [ ] **Step 1: Print the single-module uplift table**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
p = Path("/tmp/akashic-memory-answer-quality-real-full-v1/checkpoint-report/memory_comprehensive_online_eval.json")
data = json.loads(p.read_text())
rows = data["metrics"]["profile_answer_quality_uplift_vs_memory_base"]
labels = {
    "chain_memory_base": "原始记忆基线",
    "chain_tri_retrieval": "三路召回",
    "chain_graph_retrieval": "图谱召回",
    "chain_rerank_injection": "重排与注入治理",
    "chain_version_provenance": "版本链与溯源",
    "chain_all_on": "全开组合",
}
print("| 模块 | case数 | 回答命中 | 回答命中率 | 相对基线回答提升 | 证据命中 | 证据命中率 | 相对基线证据提升 | 违规率 | 平均token | 平均延迟ms |")
print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
for profile in labels:
    row = rows[profile]
    print(
        f"| {labels[profile]} | {row['case_count']} | {row['answer_success_count']} | "
        f"{row['answer_rule_pass_rate']}% | {row['answer_pass_relative_lift_percent']}% | "
        f"{row['grounding_success_count']} | {row['memory_grounding_pass_rate']}% | "
        f"{row['grounding_pass_relative_lift_percent']}% | {row['forbidden_violation_rate']}% | "
        f"{row['avg_total_token_count']} | {row['avg_latency_ms']} |"
    )
PY
```

Expected output:

- A Markdown table with six rows.
- `chain_memory_base` has `0%` relative lift by definition.
- `chain_all_on` is interpreted as combined check, not pure single-module contribution.

- [ ] **Step 2: Check per-profile completeness**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
p = Path("/tmp/akashic-memory-answer-quality-real-full-v1/checkpoint-report/memory_comprehensive_online_eval.json")
data = json.loads(p.read_text())
rows = data["metrics"]["profile_answer_quality_uplift_vs_memory_base"]
required = [
    "chain_memory_base",
    "chain_tri_retrieval",
    "chain_graph_retrieval",
    "chain_rerank_injection",
    "chain_version_provenance",
    "chain_all_on",
]
expected = 320
ok = True
print("| profile | case_count | complete |")
print("| --- | ---: | --- |")
for profile in required:
    count = int(rows.get(profile, {}).get("case_count", 0))
    complete = count == expected
    ok = ok and complete
    print(f"| {profile} | {count} | {complete} |")
if not ok:
    raise SystemExit("incomplete profile matrix")
PY
```

Expected output:

- Six rows.
- Every `complete` cell is `True`.
- If any row is incomplete, do not claim full-matrix uplift; report it as partial evidence with exact denominators.

- [ ] **Step 3: Print the ordered profile comparison table**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
p = Path("/tmp/akashic-memory-answer-quality-real-full-v1/checkpoint-report/memory_comprehensive_online_eval.json")
data = json.loads(p.read_text())
rows = data["metrics"]["chain_answer_quality_uplift_rows"]
labels = {
    "chain_memory_base": "原始记忆基线",
    "chain_tri_retrieval": "加入三路召回",
    "chain_graph_retrieval": "加入图谱召回",
    "chain_rerank_injection": "加入重排与注入治理",
    "chain_version_provenance": "加入版本链与溯源",
    "chain_all_on": "全开组合校验",
}
print("| 对比步骤 | case数 | 上一个profile | 回答命中率 | 相邻回答变化 | 相对基线回答提升 | 证据命中率 | 相邻证据变化 | 相对基线证据提升 |")
print("| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
for row in rows:
    profile = row["profile_name"]
    previous = row["previous_profile"] or "无"
    print(
        f"| {labels.get(profile, profile)} | {row['case_count']} | {labels.get(previous, previous)} | "
        f"{row['answer_rule_pass_rate']}% | {row['adjacent_answer_pass_delta_points']}pp | "
        f"{row['cumulative_answer_pass_relative_lift_percent']}% | "
        f"{row['memory_grounding_pass_rate']}% | {row['adjacent_grounding_pass_delta_points']}pp | "
        f"{row['cumulative_grounding_pass_relative_lift_percent']}% |"
    )
PY
```

Expected output:

- A Markdown table ordered by `chain_memory_base -> chain_tri_retrieval -> chain_graph_retrieval -> chain_rerank_injection -> chain_version_provenance -> chain_all_on`.
- This table answers how each existing profile compares when arranged in the planned order.
- It does not prove that the code cumulatively enabled one module after another, because current `evidence_ids_for_profile()` maps each profile to its own trace evidence source.
- `chain_all_on` is a compatibility/check row and currently uses sleep-filtered active ids.

## Task 6: Interpret The Result

**Files:**
- Read: checkpoint-only Markdown and JSON report.
- No code changes.

**Interfaces:**
- Consumes: table output from Task 5.
- Produces: concise conclusion for the user and documentation.

- [ ] **Step 1: Apply interpretation rules**

Use these rules:

- If `answer_pass_relative_lift_percent > 0`, say the module improved answer correctness relative to original memory.
- If `answer_pass_relative_lift_percent = 0`, say the module did not improve answer correctness on this dataset.
- If `answer_pass_relative_lift_percent < 0`, say the module hurt answer correctness on this dataset and inspect failure records.
- If `memory_grounding_pass_rate` improves while answer does not, say the module improves evidence use but does not yet convert into answer correctness.
- If `forbidden_violation_rate` increases, treat it as a retrieval/injection risk even if answer rate improves.
- If token or latency rises sharply, report the cost as a tradeoff, not as a failure.
- Do not call adjacent profile differences "module cumulative gains" unless the implementation has been changed to build cumulative evidence from prior steps.

- [ ] **Step 2: Check infrastructure boundary before claiming model quality**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
p = Path("/tmp/akashic-memory-answer-quality-real-full-v1/checkpoint-report/memory_comprehensive_online_eval.json")
m = json.loads(p.read_text())["metrics"]
for key in [
    "infra_passed",
    "provider_error_count",
    "timeout_count",
    "excluded_infra_failure_count",
    "case_count",
    "unique_case_count",
    "answer_quality_partial_matrix",
    "answer_quality_missing_profiles",
]:
    print(f"{key}={m.get(key)}")
PY
```

Expected output for a complete clean run:

```text
infra_passed=True
provider_error_count=0
timeout_count=0
excluded_infra_failure_count=0
case_count=1920
unique_case_count=320
answer_quality_partial_matrix=False
answer_quality_missing_profiles=[]
```

If the report is partial, say it is partial and include the exact valid `case_count`.
If any profile has fewer than `320` valid rows after excluding infrastructure failures, use the per-profile count table from Task 5 and do not present the result as a complete full-matrix conclusion.

## Task 7: Update Documentation With Real Results

**Files:**
- Modify: `my_md/memory_optimization/README.md`
- Modify: `my_md/memory_optimization/05-memory-target-metric-eval-plan.md`
- Modify: `my_md/memory_optimization/06-memory-320-baseline-plus-count-eval.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

**Interfaces:**
- Consumes: real checkpoint report and extracted tables.
- Produces: persistent project record of run setup, result tables, conclusion, and limitations.

- [ ] **Step 1: Add the real-run summary**

Record these fields:

- run path;
- config path without secrets;
- `case_count`;
- `unique_case_count`;
- `profile_count`;
- `real_llm_enabled`;
- `infra_passed`;
- `provider_error_count`;
- `timeout_count`;
- `excluded_infra_failure_count`;
- total token count;
- average latency;
- single-module uplift table;
- ordered profile comparison table;
- conclusion and known limitations.

- [ ] **Step 2: Keep wording faithful**

Use these statements:

- This is a real LLM plus real AgentLoop answer-level evaluation.
- It is still a controlled test-set evaluation, not natural production traffic.
- It does not evaluate write governance.
- It does not evaluate sleep consolidation as a separate hygiene module, but `chain_all_on` currently uses sleep-filtered active ids and must be labeled as compatibility/check evidence rather than a pure retrieval-module gain.
- It does not write production memory.
- `chain_all_on` is a combination check row, not a pure single-module gain row.

## Task 8: Verification And Commit

**Files:**
- Run checks over modified docs and existing eval code.
- Commit only relevant files.

**Interfaces:**
- Consumes: documentation updates.
- Produces: clean commit preserving the real-run evidence.

- [ ] **Step 1: Run report and syntax checks**

Run:

```bash
.venv/bin/python -m compileall memory2/eval_comprehensive_online.py scripts/run_memory_comprehensive_online_eval.py -q
```

Expected output:

```text

```

- [ ] **Step 2: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py tests/test_memory_comprehensive_online_cli.py -q -p no:cacheprovider
```

Expected output:

```text
22 passed
```

The exact runtime may vary.

- [ ] **Step 3: Check whitespace**

Run:

```bash
git diff --check
```

Expected output:

```text

```

- [ ] **Step 4: Stage only relevant files**

Run:

```bash
git add -f docs/superpowers/plans/2026-07-24-memory-answer-quality-real-llm-full-eval.md
git add my_md/memory_optimization/README.md \
  my_md/memory_optimization/05-memory-target-metric-eval-plan.md \
  my_md/memory_optimization/06-memory-320-baseline-plus-count-eval.md \
  progress.md \
  task_plan.md
```

Expected behavior:

- Do not stage `.superpowers/sdd/*.diff`.
- Do not stage unrelated dirty files.

- [ ] **Step 5: Commit**

Run:

```bash
git commit -m "docs: record memory answer quality real llm plan and results"
```

Expected behavior:

- Commit succeeds after documentation is updated.

## Self-Review

- Spec coverage: The plan covers real-model configuration, full data scale, six-profile answer/retrieval matrix, checkpoint/resume, checkpoint-only report rebuild, single-profile uplift table, ordered profile comparison table, documentation, verification, and commit.
- Placeholder scan: No `TBD`, `TODO`, or unspecified path is used. The config path is fixed to `/home/jjh/git_work/akashic-agent/config.toml`, which exists in the main workspace found during preflight discovery.
- Type consistency: Profile names match `ANSWER_QUALITY_PROFILES` in `memory2/eval_comprehensive_online.py`; CLI arguments match `scripts/run_memory_comprehensive_online_eval.py`; expected case count matches `build_quantitative_eval_cases(case_pack="comprehensive", case_set="all") = 320`.
- Review fixes applied: The plan no longer claims current profile rows are true cumulative toggles; it labels `chain_all_on` as a compatibility/check row that may include sleep-filtered ids; it requires per-profile completeness before full conclusions; it warns that `answer_debug` must not be copied or committed.
