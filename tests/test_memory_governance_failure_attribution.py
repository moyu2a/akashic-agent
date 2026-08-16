from __future__ import annotations

from memory2.eval_online_failure_attribution import governance_failure_buckets


def test_governance_failure_buckets_maps_scoring_and_infra_failures() -> None:
    buckets = governance_failure_buckets(
        [
            "missing_expected_answer_term",
            "found_forbidden_answer_term",
            "provider_error",
        ]
    )

    assert buckets == (
        "missing_expected_answer_term",
        "found_forbidden_answer_term",
        "provider_error",
    )
