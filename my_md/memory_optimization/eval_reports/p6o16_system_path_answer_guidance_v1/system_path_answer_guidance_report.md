# P6o-16 System Path Answer Guidance

## Purpose

Validate whether production-safe answer guidance can improve answer-rule pass rate after P6o-15 showed that `safe_version_replace` already controls forbidden leakage but still misses some required answer terms.

## Method

- Case pack: standard balanced small, common `20` + hard `20`.
- Modes: `current`, `safe_version_replace`, `safe_version_replace_guided`.
- Repeats: `1`.
- Real calls: `40` unique cases * `3` modes * `1` repeat = `120`.
- Checkpoint: `real_small_ab/checkpoint.jsonl`.
- Rebuilt report: `real_small_ab_rebuilt/`.
- Reports exclude raw prompt, raw query, session text, memory summaries, full answers, API keys, authorization values, and secrets.

## Results

| mode | cases | answer_rate | grounding_rate | forbidden_rate | contract_success | post_check_shadow | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| current | 40 | 25.0 | 100.0 | 27.5 | 0.0 | 0.0 | 5530.525 | 4734.875 |
| safe_version_replace | 40 | 65.0 | 100.0 | 0.0 | 100.0 | 100.0 | 5382.625 | 3261.825 |
| safe_version_replace_guided | 40 | 72.5 | 100.0 | 0.0 | 100.0 | 100.0 | 5467.7 | 3207.6 |

## Delta

- `safe_version_replace` vs `current`: answer `+40.0` points, forbidden `-27.5` points, grounding unchanged at `100.0%`, avg tokens `-147.9`.
- `safe_version_replace_guided` vs `safe_version_replace`: answer `+7.5` points, forbidden unchanged at `0.0%`, grounding unchanged at `100.0%`, avg tokens `+85.075`.
- `safe_version_replace_guided` vs `current`: answer `+47.5` points, forbidden `-27.5` points, grounding unchanged at `100.0%`, avg tokens `-62.825`.

## Comparison With P6o-15

P6o-15 used a stronger stability design: `40` unique cases * `2` modes * `3` repeats = `240` real calls. It established `safe_version_replace` as the best stable production-shaped baseline: answer `88/120 = 73.3333%`, grounding `100.0%`, forbidden `0.0%`, avg tokens `5427.0833`, and repeat answer spread only `2.5` points.

P6o-16 used a smaller exploratory A/B: `40` unique cases * `3` modes * `1` repeat = `120` real calls. In this same-run comparison, `safe_version_replace_guided` improved over unguided `safe_version_replace`: answer `29/40 = 72.5%` vs `26/40 = 65.0%`, with grounding unchanged at `100.0%`, forbidden unchanged at `0.0%`, and avg tokens still within the +5% budget.

The conclusion changed in one important way: P6o-15 proved the best stable base was candidate-governed safe version replacement; P6o-16 shows that a generic answer guidance layer can add extra lift on top of that base. The conclusion strength is different: P6o-16 validates direction and gate fit, while a repeated confirmation run is still required before treating guided replace as the new stable best profile.

## Gate

- `provider_error_count = 0`.
- `timeout_count = 0`.
- Guided grounding did not regress: `100.0% >= 100.0%`.
- Guided forbidden did not regress and stayed at zero: `0.0% == 0.0%`.
- Guided answer exceeded replace: `72.5% > 65.0%`.
- Guided avg tokens stayed within replace + 5%: `5467.7 <= 5651.7563`.
- `gate_passed = true`.

## Privacy And Rebuild Checks

- Fake smoke: `4` unique cases, `3` modes, `12` rows; guided rows had `answer_guidance_enabled = true` in metadata and contract.
- Real checkpoint lines: `120`.
- Report-only rebuild matched primary metrics for case count and mode summaries.
- Key privacy scan found no forbidden report keys.
- Value privacy scan over the 40 selected case queries, memory summaries, and replacement summaries returned `leak_count = 0`.

## Conclusion

P6o-16 passed the exploratory answer-guidance gate. Adding generic, production-safe answer guidance to the safe version replacement contract improved the real system-path answer rate from `65.0%` to `72.5%` without increasing forbidden leakage, without grounding regression, and without token blow-up.

The result supports the current diagnosis: the remaining bottleneck is evidence-to-answer expression, not recall. The guidance does not add new evidence and does not change candidate governance; it only makes the model use already-allowed evidence more directly.

## Boundaries

- This is still a controlled fixture-seeded system-path A/B, not production natural traffic.
- Production default remains `off`.
- Safe-version replace and guidance are config/eval gated and cannot be enabled by session metadata or `request.extra`.
- No graph/all-on, no new retrieval lanes, no write path change, no retry, no fallback, and no real user memory DB read.

## Next Step

Do not promote directly to production default. The next step should be a repeated confirmation run for `safe_version_replace_guided` against `safe_version_replace`, then a config-gated shadow rollout plan that records guided-vs-unguided post-check deltas without changing production replies.

## Side Conversation Follow-Up Notes

Current quality is still not sufficient for production default activation. The known issue is not mainly recall: `safe_version_replace` and `safe_version_replace_guided` both keep grounding at `100.0%` and forbidden at `0.0%`, while answer remains around the low `70%` range. This points to evidence-to-answer expression: the allowed evidence is present, but the model does not consistently produce the required concrete answer.

The next improvement should focus on the local memory evidence prompt rather than the global system prompt. A global prompt change has a wider blast radius across tools, style, multi-turn behavior, and unrelated workflows. The narrower and safer surface is the system-path memory contract / evidence block because the problem appears specifically when the model consumes memory evidence.

Recommended improvement surfaces:

- Memory block format: make allowed evidence more structured so the model can identify current facts, active versions, insufficient evidence, and forbidden boundaries without using raw forbidden/deleted ids.
- Answer guidance wording: evolve from generic guidance to a stronger production-safe answer scaffold, such as requiring concrete facts from allowed evidence, merging multiple allowed facts, and answering in the user's language.
- Prompt placement / proximity: test whether the contract works better near the user query, before the user context, or in the current system-path position.
- Failure attribution: before changing wording again, compare guided failures against unguided failures to separate evidence-present-but-not-said, evaluator term mismatch, language failure, over-refusal, and formatting/placement issues.
- Evaluator review: some misses may be semantically correct but fail required term matching; do not loosen scoring first, but inspect the failed buckets before deciding.

Suggested next matrix after repeat confirmation:

- `safe_version_replace`
- `safe_version_replace_guided`
- `safe_version_replace_structured_guided`
- `safe_version_replace_near_query_block`

The purpose is to determine whether the next lift comes from guidance content, evidence block structure, or prompt placement.
