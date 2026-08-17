# LongMemEval Global Language and Eval Credibility Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development when multi-agent tools are available, otherwise use superpowers:executing-plans. Execute phase by phase. Each phase must be reviewed before implementation and must pass its gate before the next phase starts.

**Goal:** Fix the global prompt and public long-memory evaluation issues that contaminated LongMemEval Phase A v3, then rerun Phase A v4 with comparable settings.

**Architecture:** Keep the production AgentLoop path under test, but remove unconditional Chinese language forcing globally. Public LongMemEval cases carry dataset dates through the same EvalCase/AgentLoop path, evidence rendering exposes session dates, request capture snapshots provider inputs immutably, and public reports add diagnostic scoring without overwriting deterministic metrics.

**Tech Stack:** Python 3, pytest, existing `agent` prompt assembly, `memory2` evaluation runners, JSON/JSONL, Markdown.

## Global Constraints

- Work in branch `feature/memory-governance-eval-v2`.
- Do not mutate Phase A v3 report/checkpoint/debug artifacts after recording the postmortem.
- Do not create a LongMemEval-only prompt bypass for the language issue; fix unconditional language forcing globally.
- Preserve Chinese style for Chinese user input.
- Preserve deterministic public scorer fields for v3/v4 comparability.
- Gold answer must never be written into memory or provider requests.
- Model answers must not be written back into memory.
- Phase B full run is out of scope until Phase A v4 gate passes and the user explicitly asks for it.

## Phase 0: v3 Postmortem Baseline

**Status:** Completed in commit `7c9b296`.

**Deliverables:**
- `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v3/phase_a_v3_postmortem.md`
- v3 lightweight report/checkpoint files committed.
- v3 workspace/debug/request files remain local diagnostic artifacts and are not committed.

**Gate:**
- Postmortem documents run method, true metrics, artifact paths, captured flow samples, and confirmed problems.

## Phase 1: Plan Persistence

**Deliverable:** This plan file.

**Review Checklist:**
- Confirms global language fix instead of dataset-specific prompt bypass.
- Separates prompt, date/evidence, capture, scorer, rerun, and comparison phases.
- Keeps v3 immutable and v4 comparable.
- Blocks Phase B until v4 gate and user approval.

**Gate:**
- Plan is committed before code behavior changes.

## Phase 2: Global Language Policy

**Target behavior:**
- User input language controls default response language.
- Chinese input keeps current Chinese conversational style.
- English input gets concise natural English.
- Explicit user language instruction and durable language preference can still override defaults.
- Evidence contracts do not force a language.

**Implementation outline:**
- Update `agent/persona.py` casual/work wording from unconditional Chinese to language matching.
- Update `prompts/agent.py` output format wording from unconditional Chinese to language matching.
- Update P5 evidence contract wording in `memory2/eval_answer_contract.py` to include a language-neutral same-language instruction.

**Tests:**
- Add prompt tests proving English current messages are not paired with unconditional Chinese output rules.
- Add prompt tests proving Chinese current messages still receive Chinese-style guidance.
- Add contract tests proving public P5 contract says not to change answer language and no longer says to answer in Chinese.

**Gate:**
- Focused prompt/contract tests pass.
- Existing public eval tests pass.
- Commit message: `fix(prompt): make response language follow user input`.

## Phase 3: LongMemEval Date and Evidence Rendering

**Target behavior:**
- LongMemEval `question_date` becomes the AgentLoop message timestamp for public eval cases.
- Evidence text includes `session_id` and `session_date`.
- `today/yesterday` inside session turns can be interpreted against the rendered session date.

**Implementation outline:**
- Extend `PublicLongMemoryCase` with `question_date`.
- Parse `question_date` from LongMemEval rows.
- Store it in `EvalCase.setup["public_long_memory"]["question_date"]` or equivalent setup field.
- Update public runner/comprehensive runner path to pass the parsed timestamp into `loop.process_direct(..., turn_metadata=...)` or an equivalent message timestamp path.
- Update answer-window rendering to prefix each session item with `session_id=...; session_date=...`.

**Tests:**
- Loader preserves `question_date`.
- Public EvalCase carries question date.
- Fake-provider/request capture shows current message time equals the dataset question date.
- Evidence block includes session date and session id.
- Gold answer remains absent from memory and request payload.

**Gate:**
- Focused public eval tests pass.
- Compile checks pass.
- Compatibility eval tests pass.
- Commit message: `fix(memory): use LongMemEval dates in public eval evidence`.

## Phase 4: Provider Request Snapshot Capture

**Target behavior:**
- Captured provider request is the immutable request at send time.
- Captured request does not include later assistant answer mutation.
- Captured request does not include secrets or callable callbacks.

**Implementation outline:**
- Change `_RecordingProvider` request capture to sanitized deep copy.
- Reuse the same sanitizer for provider request debug files.
- Add report metrics for capture file count and snapshot cleanliness.

**Tests:**
- Mutating the original `messages` list after `chat()` does not mutate captured request.
- Request debug file omits secret-like keys and callables.
- Fake-provider public runner capture does not include assistant answer mutation.

**Gate:**
- Capture-focused tests pass.
- Public runner smoke passes.
- Commit message: `fix(eval): snapshot provider requests for public memory eval`.

## Phase 5: Public Scoring Diagnostics

**Target behavior:**
- Deterministic score remains unchanged.
- Report adds diagnostics that explain false negatives and failure causes.

**Implementation outline:**
- Add language detection fields: `question_language`, `response_language`, `language_mismatch`.
- Add aggregate `language_mismatch_count`.
- Add abstention intent secondary scoring.
- Add preference/long-answer `semantic_review_needed` marker.
- Split evidence support fields into `literal_gold_hit`, `requires_reasoning_gold`, and `supporting_fact_hit` where deterministic inference is possible.
- Add failure attribution labels without overwriting deterministic `public_score.method`.

**Tests:**
- English gold with Chinese equivalent answer is flagged as likely scorer false negative when language mismatch is present.
- Abstention refusal is marked as intent pass.
- Preference cases are marked for semantic/rubric review.
- Report remains backward compatible with existing deterministic fields.

**Gate:**
- Scorer/report tests pass.
- Public runner smoke passes.
- Commit message: `feat(eval): add public memory scoring diagnostics`.

## Phase 6: Phase A v4 Online Rerun

**Command shape:**
- Same dataset, sample size, seed, profile, prompt variant, repeats, evidence mode, token budget, concurrency, and real LLM config as v3.
- Output directory: `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v4/`.
- Request capture enabled.

**Gate:**
- completed call count = 50.
- actual call shape = `50 * 1 * 1 * 1 = 50`.
- provider error = 0.
- timeout = 0.
- malformed checkpoint = 0.
- request capture count = 50.
- answer debug count = 50.
- tool-call style output <= 5.
- request capture snapshot has no assistant-answer mutation.
- English-question language mismatch is materially lower than v3 `46/50`.
- Temporal "missing date" failures are materially lower than v3.

**If gate fails:** Stop, write a v4 failure note, and revise the relevant phase before rerun.

## Phase 7: v3/v4 Comparison

**Deliverable:**
- `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v4/phase_a_v4_comparison.md`

**Required content:**
- v3/v4 metric comparison.
- Category-level comparison.
- Language mismatch comparison.
- Temporal failure comparison.
- Request capture cleanliness status.
- Remaining failed case table with failure attribution.
- Explicit recommendation on whether Phase B is allowed.

**Gate:**
- Comparison document committed.
- Final verification commands pass.
- Commit message: `docs(memory): compare LongMemEval phase A v3 and v4`.
