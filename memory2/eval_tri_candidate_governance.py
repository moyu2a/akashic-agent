from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from memory2.eval_comprehensive_online import evidence_ids_for_profile
from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.retrieval_governance import (
    CandidateGovernancePolicy,
    apply_retrieval_route,
    build_retrieval_routing_decision,
)


DEFAULT_TRI_FAILURE_ATTRIBUTION_JSON = (
    "my_md/memory_optimization/eval_reports/"
    "tri_retrieval_failure_attribution_v1/tri_retrieval_failure_attribution.json"
)


def build_tri_candidate_governance_report(
    case_pack: str = "comprehensive",
    tri_failure_json: str | Path = DEFAULT_TRI_FAILURE_ATTRIBUTION_JSON,
) -> dict[str, object]:
    tri_rows = _load_tri_failure_rows(Path(tri_failure_json))
    rows: list[dict[str, object]] = []
    dropped_by_reason: dict[str, int] = {}
    unprotected_dropped_by_reason: dict[str, int] = {}
    would_drop_protected_by_reason: dict[str, int] = {}
    tiered_candidate_risk_tier_counts: dict[str, int] = {}
    tiered_accepted_candidate_risk_tier_counts: dict[str, int] = {}
    tiered_deleted_risks_by_reason: dict[str, int] = {}
    failure_bucket_counts: dict[str, int] = {}
    baseline_expected_hit_count = 0
    protected_expected_hit_count = 0
    unprotected_expected_hit_count = 0
    protected_expected_hit_loss_count = 0
    unprotected_expected_hit_loss_count = 0
    should_not_candidate_count = 0
    strict_should_not_drop_count = 0
    strict_should_not_kept_count = 0

    for case in build_quantitative_eval_cases(case_pack=case_pack):
        expected_ids = _string_tuple(case.expectations.get("should_recall_ids", ()))
        if not expected_ids:
            continue
        tri_fused_ids = tuple(evidence_ids_for_profile(case, "chain_tri_retrieval"))
        should_not_ids = _string_tuple(case.expectations.get("should_not_recall_ids", ()))
        tri_failure = tri_rows.get(case.id, {})
        failure_bucket = str(
            tri_failure.get("failure_bucket") or "not_in_40_case_report"
        )
        failure_bucket_counts[failure_bucket] = (
            failure_bucket_counts.get(failure_bucket, 0) + 1
        )
        baseline_decision = build_retrieval_routing_decision(
            str(case.setup.get("query") or "")
        )
        protected_decision = baseline_decision.with_candidate_governance(
            CandidateGovernancePolicy(
                enabled=True,
                protected_expected_ids=expected_ids,
                eval_mode=True,
            )
        )
        unprotected_decision = baseline_decision.with_candidate_governance(
            CandidateGovernancePolicy(enabled=True)
        )
        candidates_by_lane = _fixture_candidates_by_lane(case, should_not_ids)
        tiered_decision = baseline_decision.with_candidate_governance(
            CandidateGovernancePolicy(
                enabled=True,
                mode="tiered",
                protected_expected_ids=expected_ids,
                eval_mode=True,
            )
        )
        baseline_candidates, _baseline_trace = apply_retrieval_route(
            baseline_decision,
            candidates_by_lane,
        )
        protected_candidates, protected_trace = apply_retrieval_route(
            protected_decision,
            candidates_by_lane,
        )
        unprotected_candidates, unprotected_trace = apply_retrieval_route(
            unprotected_decision,
            candidates_by_lane,
        )
        tiered_candidates, tiered_trace = apply_retrieval_route(
            tiered_decision,
            candidates_by_lane,
        )
        baseline_ids = _candidate_ids(baseline_candidates)
        protected_ids = _candidate_ids(protected_candidates)
        unprotected_ids = _candidate_ids(unprotected_candidates)
        tiered_counts = _dict_counts(tiered_trace.get("candidate_risk_tier_counts", {}))
        tiered_accepted_counts = _dict_counts(
            tiered_trace.get("accepted_candidate_risk_tier_counts", {})
        )
        expected_set = set(expected_ids)
        should_not_set = set(should_not_ids)
        baseline_hits = len(expected_set & baseline_ids)
        protected_hits = len(expected_set & protected_ids)
        unprotected_hits = len(expected_set & unprotected_ids)
        protected_loss = max(0, baseline_hits - protected_hits)
        unprotected_loss = max(0, baseline_hits - unprotected_hits)

        baseline_expected_hit_count += baseline_hits
        protected_expected_hit_count += protected_hits
        unprotected_expected_hit_count += unprotected_hits
        protected_expected_hit_loss_count += protected_loss
        unprotected_expected_hit_loss_count += unprotected_loss
        should_not_candidate_count += len(should_not_set & baseline_ids)
        strict_should_not_kept_count += len(should_not_set & protected_ids)
        strict_should_not_drop_count += len(
            (should_not_set & baseline_ids) - protected_ids
        )
        _merge_counts(
            dropped_by_reason,
            protected_trace.get("dropped_risks_by_reason", {}),
        )
        _merge_counts(
            unprotected_dropped_by_reason,
            unprotected_trace.get("dropped_risks_by_reason", {}),
        )
        _merge_counts(
            would_drop_protected_by_reason,
            protected_trace.get("would_drop_protected_by_reason", {}),
        )
        _merge_counts(
            tiered_candidate_risk_tier_counts,
            tiered_counts,
        )
        _merge_counts(
            tiered_accepted_candidate_risk_tier_counts,
            tiered_accepted_counts,
        )
        _merge_counts(
            tiered_deleted_risks_by_reason,
            tiered_trace.get("tiered_deleted_risks_by_reason", {}),
        )
        rows.append(
            {
                "case_id": case.id,
                "category": case.category,
                "failure_bucket": failure_bucket,
                "pass_pattern": tri_failure.get("pass_pattern"),
                "scene": protected_trace["scene"],
                "expected_id_count": len(expected_ids),
                "tri_fused_id_count": len(tri_fused_ids),
                "tri_fused_expected_overlap_count": len(
                    set(tri_fused_ids) & expected_set
                ),
                "should_not_id_count": len(should_not_ids),
                "baseline_expected_hits": baseline_hits,
                "protected_expected_hits": protected_hits,
                "unprotected_expected_hits": unprotected_hits,
                "protected_expected_hit_loss": protected_loss,
                "unprotected_expected_hit_loss": unprotected_loss,
                "baseline_candidate_count": len(baseline_candidates),
                "protected_candidate_count": len(protected_candidates),
                "unprotected_candidate_count": len(unprotected_candidates),
                "tiered_classified_candidate_count": sum(tiered_counts.values()),
                "tiered_accepted_candidate_count": len(tiered_candidates),
                "tiered_candidate_risk_tier_counts": tiered_counts,
                "tiered_accepted_candidate_risk_tier_counts": tiered_accepted_counts,
                "tiered_deleted_risks_by_reason": tiered_trace.get(
                    "tiered_deleted_risks_by_reason",
                    {},
                ),
                "tiered_delete_count": tiered_counts.get("delete", 0),
                "tiered_downgrade_count": tiered_counts.get("downgrade", 0),
                "tiered_requires_review_count": tiered_counts.get(
                    "requires_review",
                    0,
                ),
                "tiered_allow_count": tiered_counts.get("allow", 0),
                "dropped_risks_by_reason": protected_trace.get(
                    "dropped_risks_by_reason",
                    {},
                ),
                "unprotected_dropped_risks_by_reason": unprotected_trace.get(
                    "dropped_risks_by_reason",
                    {},
                ),
                "would_drop_protected_by_reason": protected_trace.get(
                    "would_drop_protected_by_reason",
                    {},
                ),
                "protected_risky_candidate_count": protected_trace.get(
                    "protected_risky_candidate_count",
                    0,
                ),
            }
        )

    metrics = {
        "case_pack": case_pack,
        "case_count": len(rows),
        "baseline_expected_hit_count": baseline_expected_hit_count,
        "protected_expected_hit_count": protected_expected_hit_count,
        "unprotected_expected_hit_count": unprotected_expected_hit_count,
        "protected_expected_hit_loss_count": protected_expected_hit_loss_count,
        "unprotected_expected_hit_loss_count": unprotected_expected_hit_loss_count,
        "should_not_candidate_count": should_not_candidate_count,
        "strict_should_not_drop_count": strict_should_not_drop_count,
        "strict_should_not_kept_count": strict_should_not_kept_count,
        "dropped_risks_by_reason": dropped_by_reason,
        "unprotected_dropped_risks_by_reason": unprotected_dropped_by_reason,
        "would_drop_protected_by_reason": would_drop_protected_by_reason,
        "tiered_candidate_risk_tier_counts": tiered_candidate_risk_tier_counts,
        "tiered_accepted_candidate_risk_tier_counts": (
            tiered_accepted_candidate_risk_tier_counts
        ),
        "tiered_deleted_risks_by_reason": tiered_deleted_risks_by_reason,
        "failure_bucket_counts": failure_bucket_counts,
    }
    return {"metrics": metrics, "case_rows": rows}


def write_tri_candidate_governance_report(
    report: Mapping[str, object],
    out_dir: Path,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "tri_candidate_governance.json"
    md_path = out_dir / "tri_candidate_governance.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    metrics = report["metrics"]
    case_rows = report["case_rows"]
    lines = [
        "# Tri Candidate Governance",
        "",
        "本报告是三路召回候选去噪和 forbidden / 冲突过滤的离线 trace 评测，不调用 LLM。",
        "",
        "## Metrics",
        "",
    ]
    if isinstance(metrics, Mapping):
        for key, value in metrics.items():
            lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Risk Tier Metrics", ""])
    if isinstance(metrics, Mapping):
        for key in (
            "tiered_candidate_risk_tier_counts",
            "tiered_accepted_candidate_risk_tier_counts",
            "tiered_deleted_risks_by_reason",
        ):
            lines.append(f"- `{key}`: `{metrics.get(key)}`")
    lines.extend(["", "## Case Rows", ""])
    lines.append(
        "| case_id | category | bucket | scene | expected | baseline_hits | "
        "protected_hits | unprotected_hits | protected_loss | unprotected_loss | "
        "baseline_candidates | protected_candidates | "
        "tiered_classified_candidate_count | tiered_accepted_candidate_count | "
        "tiered_delete_count | tiered_downgrade_count | "
        "tiered_requires_review_count | tiered_allow_count |"
    )
    lines.append(
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | "
        "---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    if isinstance(case_rows, list):
        for row in case_rows:
            if not isinstance(row, Mapping):
                continue
            lines.append(
                f"| `{row['case_id']}` | `{row['category']}` | "
                f"`{row['failure_bucket']}` | `{row['scene']}` | "
                f"{row['expected_id_count']} | {row['baseline_expected_hits']} | "
                f"{row['protected_expected_hits']} | "
                f"{row['unprotected_expected_hits']} | "
                f"{row['protected_expected_hit_loss']} | "
                f"{row['unprotected_expected_hit_loss']} | "
                f"{row['baseline_candidate_count']} | "
                f"{row['protected_candidate_count']} | "
                f"{row['tiered_classified_candidate_count']} | "
                f"{row['tiered_accepted_candidate_count']} | "
                f"{row['tiered_delete_count']} | "
                f"{row['tiered_downgrade_count']} | "
                f"{row['tiered_requires_review_count']} | "
                f"{row['tiered_allow_count']} |"
            )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def _fixture_candidates_by_lane(
    case: Any,
    should_not_ids: tuple[str, ...],
) -> dict[str, list[dict[str, object]]]:
    scope = dict(case.setup.get("scope") or {})
    should_not = set(should_not_ids)
    candidates: list[dict[str, object]] = []
    for item in case.setup.get("memory_items", []):
        if not isinstance(item, Mapping):
            continue
        candidate = dict(item)
        candidate["scope_match"] = (
            str(candidate.get("scope_channel") or "")
            == str(scope.get("channel") or "")
            and str(candidate.get("scope_chat_id") or "")
            == str(scope.get("chat_id") or "")
        )
        candidate["should_not_recall"] = str(candidate.get("id") or "") in should_not
        candidates.append(candidate)
    return {
        "semantic": candidates,
        "keyword": list(candidates),
        "provenance": list(candidates),
        "graph": list(candidates),
    }


def _load_tri_failure_rows(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("case_rows", [])
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("case_id") or ""): dict(row)
        for row in rows
        if isinstance(row, Mapping)
    }


def _candidate_ids(candidates: list[dict[str, Any]]) -> set[str]:
    return {
        str(item.get("id") or item.get("memory_id") or "")
        for item in candidates
    }


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, list | tuple):
        return tuple(str(item) for item in value)
    return ()


def _merge_counts(target: dict[str, int], source: object) -> None:
    if not isinstance(source, Mapping):
        return
    for reason, count in source.items():
        target[str(reason)] = target.get(str(reason), 0) + int(count or 0)


def _dict_counts(source: object) -> dict[str, int]:
    if not isinstance(source, Mapping):
        return {}
    return {str(reason): int(count or 0) for reason, count in source.items()}
