# Memory Phase 6d Quantitative Uplift Design

## Status

Proposed design for review.

Date: 2026-07-19

## Background

The project now has three usable measurement layers:

- Phase 6a: deterministic fixture evaluation for the Phase 1-5 shadow traces.
- Phase 6b: real-sample and answer-level evaluation with explicit real-LLM gating and repeat runs.
- Phase 6c-1: offline uplift proxy report that can compare phase-level shadow traces against the fixture baseline.

These layers prove that the memory pipeline can be measured, but they do not yet give one clear, user-facing answer to the question:

- What does each memory feature add by itself?
- What does the complete memory stack add when all features are enabled together?
- How much of the observed gain comes from answer quality, grounding quality, or safety reduction?

Phase 6d is the missing quantification layer. It should turn the existing feature flags, fixtures, and answer-level evaluation into a single comparison matrix that can report:

1. per-feature uplift;
2. cumulative uplift;
3. the delta from baseline to full stack;
4. cost and safety trade-offs alongside the main score.

The goal is not to invent a new benchmark. The goal is to standardize the project's current evaluation so the team can say, for example, “adding feature X improved the main score by Y points” and “enabling the full stack improved the score by Z points over baseline.”

## Decision

Use a single fixed evaluation set and a fixed profile matrix that compares:

- baseline (`off`)
- each individual feature switch turned on by itself
- the full stack with all feature switches on

Compute one headline score from existing answer and grounding metrics, then report each profile as an absolute score and as uplift over `off`.

The design should be conservative:

- reuse the current fixture cases and real-sample cases where possible;
- keep the existing `off / shadow / active` semantics unchanged;
- do not introduce a new runtime mode;
- keep the result deterministic for fixture-backed cases and repeatable for gated real-LLM runs;
- do not claim production uplift unless the report is clearly marked as measured on the selected evaluation set.

## Recommended Metric Model

### Primary score

Use a weighted score on a 0-100 scale:

- `answer_rule_pass_rate`: 70%
- `memory_grounding_pass_rate`: 20%
- `forbidden_violation_rate` penalty: 10%

Suggested formula:

```text
main_score = 0.7 * answer_rule_pass_rate
           + 0.2 * memory_grounding_pass_rate
           + 0.1 * (100 - forbidden_violation_rate)
```

Interpretation:

- `answer_rule_pass_rate` captures whether the final answer matches the expected behavior.
- `memory_grounding_pass_rate` captures whether the right memory evidence actually entered the answer path.
- `forbidden_violation_rate` keeps the score honest when a profile introduces unsafe or irrelevant behavior.

The exact weights are project choices, not an industry standard. The point is to keep one headline number while still showing the raw components.

### Supporting metrics

The report must always expose the raw parts of the score:

- `answer_rule_pass_rate`
- `memory_grounding_pass_rate`
- `forbidden_violation_rate`
- `token_cost`
- `latency_ms`
- `case_count`
- `repeat_count`

### Uplift definitions

For every profile:

- `absolute_score = main_score(profile)`
- `uplift = absolute_score - main_score(off)`
- `uplift_pct = uplift / main_score(off)` when the baseline score is non-zero

For the cumulative stack:

- `total_uplift = main_score(all_on) - main_score(off)`

For per-feature runs:

- `feature_uplift(feature_i) = main_score(feature_i_on) - main_score(off)`

## Feature Matrix

Phase 6d should evaluate the following switch families, one at a time and then together:

1. write-value scoring
2. tri-retrieval / RRF routing
3. graph retrieval
4. rerank and injection governance
5. version chain and provenance checks
6. sleep consolidation
7. answer-level evidence debug / repeat evaluation as measurement support, not as a product feature

The full-stack run should enable all feature families together.

## Evaluation Profiles

The report should compare these profile groups:

- `off`
- `write_value_only`
- `tri_retrieval_only`
- `graph_only`
- `rerank_only`
- `version_provenance_only`
- `sleep_only`
- `all_on`

The exact runtime mapping can be built from the existing `memory_experiments` feature switches. The important part is the comparison contract, not the internal switch names.

## Data Sources

Phase 6d should reuse the data sources that already exist:

- fixture-backed eval cases from Phase 6a;
- answer-level repeat runs from Phase 6b-4;
- offline uplift proxy metrics from Phase 6c-1;
- existing memory and observe trace fields where the current runtime already emits them.

When a metric is not available for a profile, the report should explicitly say `unavailable` instead of silently dropping the field.

## Outputs

Phase 6d should produce a report that contains:

- the raw score for each profile;
- the uplift over baseline for each profile;
- the cumulative uplift for `all_on`;
- the per-feature contribution table;
- the cost and latency deltas;
- the selected headline score and the formula used;
- the evaluation set and run identity.

Minimum fields to report:

- `baseline_score`
- `profile_score`
- `uplift`
- `uplift_pct`
- `answer_rule_pass_rate`
- `memory_grounding_pass_rate`
- `forbidden_violation_rate`
- `token_cost_delta`
- `latency_delta_ms`
- `main_score`
- `feature_name`
- `profile_name`

## Non-Goals

- Changing the behavior of memory features themselves.
- Adding a new runtime toggle system.
- Declaring statistical significance without a proper run design.
- Replacing the existing phase docs or the current uplift proxy report.
- Turning Phase 6d into a generic benchmark framework.

## Design Constraints

- The same evaluation set must be used for all profile comparisons in one report.
- Baseline and experimental profiles must be run against the same case set.
- The report must clearly separate raw metrics, weighted score, and uplift.
- The score formula must be documented in the report itself.
- The report must make it obvious when a measurement is derived from real-LLM repeat runs versus fixture-only offline runs.
- The implementation should stay compatible with the current memory plugin experiment model and not modify `AgentLoop`.

## Risks and Mitigations

### Risk: headline score hides important trade-offs

Mitigation: always print the raw submetrics next to the main score, and keep token cost and latency separate from the score.

### Risk: different runs use different case mixes

Mitigation: fix the evaluation set for each report and print the case list or case hash.

### Risk: overclaiming production improvement

Mitigation: label the report as evaluation-set uplift, not production uplift, unless a separate production measurement is explicitly performed.

### Risk: features interact non-linearly

Mitigation: report single-feature runs and the full-stack run side by side so interaction effects are visible.

## Score Policy

The first published 6d report uses answer quality as the main signal and grounding as the supporting signal. The headline score keeps the default weighting above, and the raw grounding metric remains visible for diagnosis and comparison.
