# Memory P6o5 Small Real LLM AB Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the bounded P6o-5 real LLM A/B matrix for tri retrieval, candidate governance, answer contract, and governed production-safe answer contract, then record data-backed conclusions.

**Architecture:** Reuse the existing comprehensive online eval CLI and keep production behavior unchanged. Add one focused scaled fake-provider CLI/report-shape regression for the P6o-5 matrix, run a full fake-provider smoke before any real calls, then run the real LLM matrix with checkpointing and sanitized committed reports. P6o-4 post-check shadow metrics are interpreted as injected context inclusion diagnostics, not proof that the model cited those ids in the answer.

**Tech Stack:** Python 3.14, pytest, existing `scripts/run_memory_comprehensive_online_eval.py`, existing `memory2.eval_comprehensive_online`, JSON/Markdown eval reports, checkpoint JSONL under `/tmp`.

## Global Constraints

- Worktree: `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`.
- Do not sync remote/main in this plan unless the user explicitly redirects.
- Do not push without explicit user instruction.
- Do not modify production `AgentLoop`, `Reasoner`, `ToolExecutor`, `ToolRegistry`, production memory writes, production prompts, or the old `Retriever.retrieve()` return contract.
- Real LLM calls are allowed only after the fake-provider matrix smoke and artifact checks pass.
- P6o-5 matrix shape is fixed: common `20` + hard `20`, `4` profiles, prompt variant `baseline`, repeat `1`, expected `160` completed calls.
- Required profiles:
  - `chain_tri_retrieval`
  - `chain_tri_candidate_governance`
  - `chain_tri_answer_contract`
  - `chain_tri_governed_answer_contract`
- Do not write raw prompt, raw session text, raw memory summaries, full answers, answer debug artifacts, or API keys into committed report/docs.
- Use a temp empty `--real-memory-workspace` for fake and real runs so real memory DB sampling cannot leak content into reports.
- Store live checkpoint JSONL under `/tmp/akashic-memory-p6o5-small-online/`, not in git-tracked docs.
- Success gate:
  - zero provider errors, zero timeouts, zero excluded infra failures;
  - `case_count = 160`, `unique_case_count = 40`, `profile_count = 4`, `prompt_variant_count = 1`, `repeat_count = 1`;
  - governed answer contract should preserve or improve answer rate versus strict candidate governance and should not show obvious token blow-up versus `chain_tri_answer_contract`;
  - forbidden rate should not regress versus raw `chain_tri_retrieval`;
  - conclusions must label this as a small controlled eval, not production natural-traffic proof.

---

## File Structure

- Modify `tests/test_memory_comprehensive_online_cli.py`
  - Add one scaled CLI fake-provider regression for the P6o-5 four-profile matrix and post-check shadow aggregate.
- Create report output during execution:
  - `my_md/memory_optimization/eval_reports/p6o5_governed_answer_contract_small_online_v1/memory_comprehensive_online_eval.json`
  - `my_md/memory_optimization/eval_reports/p6o5_governed_answer_contract_small_online_v1/memory_comprehensive_online_eval.md`
- Modify documentation after the run:
  - `my_md/memory_optimization/README.md`
  - `my_md/memory_optimization/02-memory-quality-metrics.md`
  - `my_md/memory_optimization/03-memory-governance-design.md`
  - `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
  - `task_plan.md`
  - `progress.md`

---

### Task 0: Confirm P6o-5 Baseline

**Files:**
- Modify: none

**Interfaces:**
- Consumes: current `memory-next` worktree after P6o-4.
- Produces: known baseline for P6o-5 execution.

- [ ] **Step 1: Confirm linked worktree and branch**

Run:

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
BRANCH=$(git branch --show-current)
printf 'GIT_DIR=%s\nGIT_COMMON=%s\nBRANCH=%s\n' "$GIT_DIR" "$GIT_COMMON" "$BRANCH"
git rev-parse --show-superproject-working-tree 2>/dev/null || true
```

Expected:

```text
BRANCH=memory-next
```

`GIT_DIR` and `GIT_COMMON` should differ because this is already a linked worktree; `show-superproject-working-tree` should be empty.

- [ ] **Step 2: Inspect status and recent commits**

Run:

```bash
git status --short --branch
git log --oneline -8
```

Expected: recent commits include P6o-4 handoff:

```text
ca0f1ee docs: record answer post-check shadow handoff
9f3828c test: cover p6o4 answer post-check smoke
d46646f feat: record governed answer post-check shadow
b28af05 feat: add answer post-check shadow helper
```

---

### Task 1: Add Scaled P6o-5 Fake-Provider CLI Regression

**Files:**
- Modify: `tests/test_memory_comprehensive_online_cli.py`

**Interfaces:**
- Consumes:
  - CLI flags `--balanced-small`, `--common-limit`, `--hard-limit`, `--profiles`, `--fake-provider`, `--real-memory-workspace`.
  - Existing report metrics `answer_post_check_shadow`, `profile_metadata`, `profile_summaries`.
- Produces:
  - Test `test_comprehensive_online_cli_p6o5_scaled_fake_provider_matrix_shape()`.

- [ ] **Step 1: Write the matrix-shape test**

Append this test to `tests/test_memory_comprehensive_online_cli.py`:

```python
def test_comprehensive_online_cli_p6o5_scaled_fake_provider_matrix_shape(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "reports"
    workspace = tmp_path / "workspace"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_comprehensive_online_eval.py",
            "--workspace",
            str(workspace),
            "--out-dir",
            str(output_dir),
            "--fake-provider",
            "--case-pack",
            "standard",
            "--balanced-small",
            "--common-limit",
            "2",
            "--hard-limit",
            "2",
            "--profiles",
            (
                "chain_tri_retrieval,"
                "chain_tri_candidate_governance,"
                "chain_tri_answer_contract,"
                "chain_tri_governed_answer_contract"
            ),
            "--prompt-variants",
            "baseline",
            "--repeats",
            "1",
            "--checkpoint-jsonl",
            str(tmp_path / "checkpoint.jsonl"),
            "--real-memory-workspace",
            str(tmp_path / "empty-real-workspace"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (output_dir / "memory_comprehensive_online_eval.json").read_text(
            encoding="utf-8"
        )
    )
    markdown = (output_dir / "memory_comprehensive_online_eval.md").read_text(
        encoding="utf-8"
    )

    assert payload["metrics"]["case_count"] == 16
    assert payload["metrics"]["unique_case_count"] == 4
    assert payload["metrics"]["completed_call_count"] == 16
    assert payload["metrics"]["profile_count"] == 4
    assert payload["metrics"]["prompt_variant_count"] == 1
    assert payload["metrics"]["repeat_count"] == 1
    assert payload["metrics"]["provider_error_count"] == 0
    assert payload["metrics"]["timeout_count"] == 0
    assert set(payload["metrics"]["profile_summaries"]) == {
        "chain_tri_retrieval",
        "chain_tri_candidate_governance",
        "chain_tri_answer_contract",
        "chain_tri_governed_answer_contract",
    }
    assert payload["metrics"]["answer_post_check_shadow"]["case_count"] == 4
    assert payload["metrics"]["answer_post_check_shadow"]["enabled_case_count"] == 4
    assert payload["metrics"]["profile_metadata"][
        "chain_tri_governed_answer_contract"
    ]["production_safe_evidence_contract"] is True
    case_records = payload["case_records"]
    unique_common_ids = {row["case_id"] for row in case_records if str(row["case_id"]).startswith("common_")}
    unique_hard_ids = {row["case_id"] for row in case_records if str(row["case_id"]).startswith("hard_")}
    assert len(unique_common_ids) == 2
    assert len(unique_hard_ids) == 2
    assert {row["prompt_variant"] for row in case_records} == {"baseline"}
    assert {row["repeat_index"] for row in case_records} == {0}
    assert "## Answer Post-Check Shadow" in markdown
    assert "production_safe_evidence_contract" in markdown
    assert "raw_prompt" not in markdown
    assert "full_answer" not in markdown
    assert "session_text" not in markdown
```

- [ ] **Step 2: Run the focused CLI test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_cli.py::test_comprehensive_online_cli_p6o5_scaled_fake_provider_matrix_shape -q -p no:cacheprovider
```

Expected:

```text
1 passed
```

If this fails for a real CLI/report gap, fix only the owning eval/CLI code listed in Step 3 and rerun this step.

- [ ] **Step 3: Implement only if the test fails for a real CLI/report gap**

Allowed files for a real fix:

```text
scripts/run_memory_comprehensive_online_eval.py
memory2/eval_comprehensive_online.py
```

Forbidden fixes:

```text
agent/looping/
agent/reasoner/
agent/tools/
plugins/default_memory/engine.py
```

- [ ] **Step 4: Commit Task 1**

Run:

```bash
git add tests/test_memory_comprehensive_online_cli.py scripts/run_memory_comprehensive_online_eval.py memory2/eval_comprehensive_online.py
git commit -m "test: cover p6o5 small online matrix shape"
```

If only the test file changed, `git add` will stage only that file.

---

### Task 2: Run Fake-Provider P6o-5 Matrix Smoke

**Files:**
- Modify: none
- Create under `/tmp`: fake workspace, report directory, checkpoint JSONL.

**Interfaces:**
- Consumes: exact P6o-5 profile list and balanced small selector.
- Produces: fake-provider aggregate report proving matrix shape and report privacy before real calls.

- [ ] **Step 1: Run fake-provider smoke**

Run:

```bash
rm -rf /tmp/akashic-memory-p6o5-small-fake
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-p6o5-small-fake/workspace \
  --out-dir /tmp/akashic-memory-p6o5-small-fake/reports \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_tri_retrieval,chain_tri_candidate_governance,chain_tri_answer_contract,chain_tri_governed_answer_contract \
  --prompt-variants baseline \
  --repeats 1 \
  --fake-provider \
  --checkpoint-jsonl /tmp/akashic-memory-p6o5-small-fake/checkpoint/memory_comprehensive_online_eval.checkpoint.jsonl \
  --timeout-s 60 \
  --concurrency 1 \
  --real-memory-workspace /tmp/akashic-memory-p6o5-small-fake/empty-real-memory
```

Expected: command exits `0` and prints both report paths.

- [ ] **Step 2: Assert fake smoke artifact integrity**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path

base = Path("/tmp/akashic-memory-p6o5-small-fake/reports")
payload = json.loads((base / "memory_comprehensive_online_eval.json").read_text(encoding="utf-8"))
metrics = payload["metrics"]
profiles = set(metrics["profile_summaries"])
expected = {
    "chain_tri_retrieval",
    "chain_tri_candidate_governance",
    "chain_tri_answer_contract",
    "chain_tri_governed_answer_contract",
}
assert metrics["real_llm_enabled"] is False
assert metrics["case_count"] == 160
assert metrics["unique_case_count"] == 40
assert metrics["completed_call_count"] == 160
assert metrics["profile_count"] == 4
assert metrics["prompt_variant_count"] == 1
assert metrics["repeat_count"] == 1
assert metrics["provider_error_count"] == 0
assert metrics["timeout_count"] == 0
assert profiles == expected
assert metrics["answer_post_check_shadow"]["case_count"] == 40
assert metrics["answer_post_check_shadow"]["enabled_case_count"] == 40
case_records = payload["case_records"]
unique_common_ids = {row["case_id"] for row in case_records if str(row["case_id"]).startswith("common_")}
unique_hard_ids = {row["case_id"] for row in case_records if str(row["case_id"]).startswith("hard_")}
assert len(unique_common_ids) == 20
assert len(unique_hard_ids) == 20
assert {row["prompt_variant"] for row in case_records} == {"baseline"}
assert {row["repeat_index"] for row in case_records} == {0}
json_text = (base / "memory_comprehensive_online_eval.json").read_text(encoding="utf-8")
md_text = (base / "memory_comprehensive_online_eval.md").read_text(encoding="utf-8")
for text in (json_text, md_text):
    for forbidden in (
        "raw_prompt",
        "raw_answer",
        "answer_text",
        "evidence_block_text",
        "api_key",
        "Authorization",
        "Bearer ",
    ):
        assert forbidden not in text
privacy = metrics
assert privacy["raw_query_included"] is False
assert privacy["raw_memory_summary_included"] is False
assert privacy["prompt_included"] is False
assert privacy["session_text_included"] is False
assert privacy["full_answer_included"] is False
print("fake p6o5 artifact integrity passed")
PY
```

Expected:

```text
fake p6o5 artifact integrity passed
```

---

### Task 3: Run Real LLM P6o-5 Small Matrix

**Files:**
- Create:
  - `my_md/memory_optimization/eval_reports/p6o5_governed_answer_contract_small_online_v1/memory_comprehensive_online_eval.json`
  - `my_md/memory_optimization/eval_reports/p6o5_governed_answer_contract_small_online_v1/memory_comprehensive_online_eval.md`
- Create under `/tmp`:
  - `/tmp/akashic-memory-p6o5-small-online/checkpoint/memory_comprehensive_online_eval.checkpoint.jsonl`
  - `/tmp/akashic-memory-p6o5-small-online/workspace/`

**Interfaces:**
- Consumes: `config.toml` provider configuration and existing real LLM opt-in gate.
- Produces: one bounded real LLM A/B report with `160` completed calls.

- [ ] **Step 1: Run real LLM matrix**

Run:

```bash
rm -rf /tmp/akashic-memory-p6o5-small-online
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-p6o5-small-online/workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o5_governed_answer_contract_small_online_v1 \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_tri_retrieval,chain_tri_candidate_governance,chain_tri_answer_contract,chain_tri_governed_answer_contract \
  --prompt-variants baseline \
  --repeats 1 \
  --enable-real-llm \
  --checkpoint-jsonl /tmp/akashic-memory-p6o5-small-online/checkpoint/memory_comprehensive_online_eval.checkpoint.jsonl \
  --timeout-s 60 \
  --concurrency 1 \
  --real-memory-workspace /tmp/akashic-memory-p6o5-small-online/empty-real-memory
```

Expected: exits `0` if there are no provider/timeout infra failures. If interrupted, rerun with the same command plus `--resume`.

- [ ] **Step 2: If needed, rebuild report from checkpoint without new LLM calls**

Run only if Step 1 was interrupted or report generation needs to be repeated:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-p6o5-small-online/workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o5_governed_answer_contract_small_online_v1 \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_tri_retrieval,chain_tri_candidate_governance,chain_tri_answer_contract,chain_tri_governed_answer_contract \
  --prompt-variants baseline \
  --repeats 1 \
  --enable-real-llm \
  --checkpoint-jsonl /tmp/akashic-memory-p6o5-small-online/checkpoint/memory_comprehensive_online_eval.checkpoint.jsonl \
  --checkpoint-report-only \
  --exclude-infra-failures \
  --real-memory-workspace /tmp/akashic-memory-p6o5-small-online/empty-real-memory
```

Expected: no new provider calls; `checkpoint_report_only = True`. If `excluded_infra_failure_count > 0`, document the run as partial and do not claim the complete P6o-5 success gate. If the rebuilt Markdown still contains the generic old full-matrix wording `2560-run`, annotate the committed P6o-5 docs that the report is a `160`-call small matrix and do not rely on that generic wording as the P6o-5 conclusion.

- [ ] **Step 3: Assert real report integrity and print comparison data**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path

base = Path("my_md/memory_optimization/eval_reports/p6o5_governed_answer_contract_small_online_v1")
payload = json.loads((base / "memory_comprehensive_online_eval.json").read_text(encoding="utf-8"))
metrics = payload["metrics"]
expected_profiles = [
    "chain_tri_retrieval",
    "chain_tri_candidate_governance",
    "chain_tri_answer_contract",
    "chain_tri_governed_answer_contract",
]
assert metrics["real_llm_enabled"] is True
assert metrics["case_count"] == 160
assert metrics["unique_case_count"] == 40
assert metrics["completed_call_count"] == 160
assert metrics["profile_count"] == 4
assert metrics["prompt_variant_count"] == 1
assert metrics["repeat_count"] == 1
assert metrics["provider_error_count"] == 0
assert metrics["timeout_count"] == 0
assert metrics.get("excluded_infra_failure_count", 0) == 0
assert metrics.get("partial_due_to_infra_failure", False) is False
assert set(metrics["profile_summaries"]) == set(expected_profiles)
assert metrics["answer_post_check_shadow"]["case_count"] == 40
case_records = payload["case_records"]
unique_common_ids = {row["case_id"] for row in case_records if str(row["case_id"]).startswith("common_")}
unique_hard_ids = {row["case_id"] for row in case_records if str(row["case_id"]).startswith("hard_")}
assert len(unique_common_ids) == 20
assert len(unique_hard_ids) == 20
assert {row["prompt_variant"] for row in case_records} == {"baseline"}
assert {row["repeat_index"] for row in case_records} == {0}
json_text = (base / "memory_comprehensive_online_eval.json").read_text(encoding="utf-8")
md_text = (base / "memory_comprehensive_online_eval.md").read_text(encoding="utf-8")
for text in (json_text, md_text):
    for forbidden in (
        "raw_prompt",
        "raw_answer",
        "answer_text",
        "evidence_block_text",
        "api_key",
        "Authorization",
        "Bearer ",
    ):
        assert forbidden not in text
assert metrics["raw_query_included"] is False
assert metrics["raw_memory_summary_included"] is False
assert metrics["prompt_included"] is False
assert metrics["session_text_included"] is False
assert metrics["full_answer_included"] is False

print("profile,answer_success,answer_rate,grounding_rate,forbidden_rate,avg_tokens")
for profile in expected_profiles:
    row = metrics["profile_summaries"][profile]
    print(
        profile,
        row["answer_success_count"],
        row["answer_rule_pass_rate"],
        row["memory_grounding_pass_rate"],
        row["forbidden_violation_rate"],
        row["avg_total_token_count"],
        sep=",",
    )
print("total_token_count", metrics["total_token_count"])
print("avg_total_token_count", metrics["avg_total_token_count"])
print("post_check_shadow", metrics["answer_post_check_shadow"])
PY
```

Expected: assertion success and a CSV-like metric table in stdout.

---

### Task 4: Update Docs and Planning Records

**Files:**
- Modify: `my_md/memory_optimization/README.md`
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`
- Modify: `my_md/memory_optimization/03-memory-governance-design.md`
- Modify: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
- Modify: `task_plan.md`
- Modify: `progress.md`

**Interfaces:**
- Consumes: P6o-5 real report metrics and fake smoke result.
- Produces: documented conclusion and next-step boundary.

- [ ] **Step 1: Extract P6o-5 metrics**

Run the Step 3 assertion/print command from Task 3 and keep the exact stdout numbers for documentation.

- [ ] **Step 2: Update memory optimization docs**

Add a P6o-5 section with these facts:

```text
Report:
my_md/memory_optimization/eval_reports/p6o5_governed_answer_contract_small_online_v1/memory_comprehensive_online_eval.{json,md}

Matrix:
common 20 + hard 20, baseline prompt, repeat 1, 4 profiles, 160 completed real LLM calls.

Profiles:
chain_tri_retrieval
chain_tri_candidate_governance
chain_tri_answer_contract
chain_tri_governed_answer_contract

Boundary:
small controlled eval, not production natural traffic;
P6o-4 post-check shadow indicates injected context inclusion, not proven answer citation use;
no production AgentLoop/retrieval/write/prompt behavior changed.
```

Record the per-profile table from Task 3:

```text
profile | answer_success | answer_rate | grounding_rate | forbidden_rate | avg_tokens
```

State the comparison conclusion only from the observed data:

```text
chain_tri_retrieval = raw tri recall + normal prompt injection
chain_tri_candidate_governance = candidate filtering only
chain_tri_answer_contract = oracle diagnostic answer constraints
chain_tri_governed_answer_contract = candidate governance + production-safe evidence contract + post-check shadow
```

- [ ] **Step 3: Update `task_plan.md` and `progress.md`**

Add a `2026-07-28 Memory P6o5 Small Real LLM AB` entry with:

```text
Goal, exact matrix shape, fake smoke result, real report path, per-profile metrics, post-check shadow aggregate, conclusion, constraints, verification commands, and commit hash after commit.
```

- [ ] **Step 4: Commit docs**

Run:

```bash
git add my_md/memory_optimization/README.md \
  my_md/memory_optimization/02-memory-quality-metrics.md \
  my_md/memory_optimization/03-memory-governance-design.md \
  my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md \
  my_md/memory_optimization/eval_reports/p6o5_governed_answer_contract_small_online_v1/memory_comprehensive_online_eval.json \
  my_md/memory_optimization/eval_reports/p6o5_governed_answer_contract_small_online_v1/memory_comprehensive_online_eval.md \
  task_plan.md progress.md
git commit -m "docs: record p6o5 small online governed answer contract"
```

---

### Task 5: Final Verification

**Files:**
- Modify: none unless verification finds a real issue.

**Interfaces:**
- Consumes: all P6o-5 changes.
- Produces: final verification evidence and local commits.

- [ ] **Step 1: Run focused regression**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py tests/test_memory_answer_post_check.py tests/test_memory_comprehensive_online_eval.py tests/test_memory_comprehensive_online_cli.py tests/test_memory_retrieval_governance.py tests/test_memory_tri_candidate_governance.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 2: Run compile check**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q memory2 scripts tests
```

Expected: exit `0`.

- [ ] **Step 3: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: exit `0`.

- [ ] **Step 4: Commit plan file**

Run:

```bash
git add -f docs/superpowers/plans/2026-07-28-memory-p6o5-small-real-llm-ab.md
git commit -m "docs: add p6o5 small real llm ab plan"
```

- [ ] **Step 5: Record final status**

Run:

```bash
git status --short --branch
git log --oneline -8
```

Expected: local branch contains P6o-5 commits and no unexpected tracked dirty files.

---

## Expected P6o-5 Conclusion Shape

After execution, the conclusion should answer these questions with observed numbers:

- Does `chain_tri_governed_answer_contract` recover answer rate compared with strict candidate governance alone?
- Does candidate governance reduce forbidden risk compared with raw tri retrieval?
- Does the production-safe evidence contract avoid the oracle dependency of `chain_tri_answer_contract` while staying competitive?
- Did token usage grow materially versus `chain_tri_answer_contract` or raw tri retrieval?
- What did the answer post-check shadow flag, remembering that its id fields mean injected context inclusion, not proven citation use?

If the real report violates infra gates, the only valid conclusion is that P6o-5 is partial or blocked by infrastructure; do not infer model-quality direction from incomplete rows.
