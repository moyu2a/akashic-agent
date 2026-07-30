# P6o-17 Guided Repeat Stability Blocked Report

## Purpose

Validate whether `safe_version_replace_guided` remains better than `safe_version_replace` under the same 3-repeat real LLM stability methodology used by P6o-15.

## Plan And Review

- Plan: `docs/superpowers/plans/2026-07-29-memory-p6o17-guided-repeat-stability.md`.
- Plan review found no Critical issues.
- Important review fixes were applied before execution:
  - real guided rows must prove `answer_guidance_enabled = true` in metadata and contract;
  - unguided replace rows must remain unguided;
  - token metrics must be available before the token gate can pass;
  - checkpoint report-only rebuild must verify valid input rows and malformed line count;
  - real eval workspace must be fresh to avoid retry contamination;
  - P6o-15 is treated as historical context, not a hard cross-run gate.

## Fake Smoke

- Path: `my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/fake_smoke/`.
- Case pack: standard balanced small, common `2` + hard `2`.
- Modes: `safe_version_replace`, `safe_version_replace_guided`.
- Repeats: `3`.
- Result:
  - `unique_case_count = 4`;
  - `mode_count = 2`;
  - `repeat_count = 3`;
  - `case_count = 24`;
  - guided rows: `12`;
  - all guided metadata flags enabled: `true`;
  - all guided contract flags enabled: `true`.

## Real Run Attempt

- Intended matrix: standard case pack, common `20` + hard `20`, `2` modes, `3` repeats, `240` real calls.
- Real workspace freshness check passed for `/tmp/akashic-p6o17-real-workspace-20260729-v1`.
- Command was started with checkpoint/resume enabled.
- The run was interrupted after repeated provider failures to avoid spending time on invalid rows.
- Exit code after interrupt: `130`.
- Observed provider failure in command output: DeepSeek API returned `402 Insufficient Balance`.

## Partial Checkpoint Evidence

- Checkpoint path: `my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/real_repeat/checkpoint.jsonl`.
- Checkpoint rows before interrupt: `140`.
- Mode split:
  - `safe_version_replace`: `70`;
  - `safe_version_replace_guided`: `70`.
- Checkpoint report-only rebuild path: `my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/real_repeat_partial_rebuilt/`.
- Partial rebuilt metrics:
  - `case_count = 140`;
  - `unique_case_count = 40`;
  - `mode_count = 2`;
  - `repeat_count = 2`;
  - `checkpoint_input_count = 140`;
  - `malformed_checkpoint_line_count = 0`;
  - `provider_error_count = 140`;
  - `timeout_count = 0`;
  - `token_metrics_available = false` for both modes.

## Conclusion

P6o-17 did not produce a valid real LLM performance conclusion. The fake smoke proves the eval shape and guided flags are wired correctly, but the real repeat stability gate cannot run because the configured provider returned `402 Insufficient Balance`.

Do not compare guided vs unguided answer rates from this partial run. The partial rebuilt report has `provider_error_count = 140` and no token metrics, so answer, grounding, forbidden, token, and latency values from the partial rebuilt report are infrastructure-failure artifacts.

## Next Step

After provider balance or config is restored, rerun P6o-17 from a fresh real workspace and a fresh or deliberately cleaned checkpoint. The valid gate still requires the full `240` rows, zero provider errors, zero timeouts, real guided/unguided flag checks, token metrics availability, checkpoint health, and same-run guided-vs-replace stability comparison.
