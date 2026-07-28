from __future__ import annotations

from dataclasses import replace

from memory2.eval_answer_contract import (
    build_governed_tri_answer_contract,
    build_production_governed_tri_evidence_contract,
    build_tri_answer_contract,
    render_answer_contract_block,
    render_production_evidence_contract_block,
    tri_governed_answer_contract_evidence_ids,
    tri_answer_contract_evidence_ids,
)
from memory2.eval_quantitative_cases import build_quantitative_eval_cases


def _case_with_should_not_in_tri():
    for case in (
        build_quantitative_eval_cases(case_set="common", limit=20, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=20, case_pack="standard")
    ):
        tri_ids = set(build_tri_answer_contract(case).tri_ids)
        should_not = set(case.expectations["should_not_recall_ids"])
        if tri_ids & should_not:
            return case
    raise AssertionError("fixture must include at least one tri should-not candidate")


def test_contract_keeps_expected_ids_and_marks_forbidden_candidates() -> None:
    case = _case_with_should_not_in_tri()

    contract = build_tri_answer_contract(case)

    expected_ids = tuple(str(item) for item in case.expectations["should_recall_ids"])
    should_not_ids = set(str(item) for item in case.expectations["should_not_recall_ids"])
    assert set(expected_ids) <= set(contract.must_use_ids)
    assert set(contract.forbidden_ids) == (set(contract.tri_ids) & should_not_ids)
    assert set(contract.forbidden_ids).isdisjoint(contract.allowed_evidence_ids)
    assert contract.diagnostic_eval_only is True


def test_contract_evidence_ids_preserve_tri_order_and_remove_forbidden() -> None:
    case = _case_with_should_not_in_tri()
    tri_ids = build_tri_answer_contract(case).tri_ids
    forbidden = set(str(item) for item in case.expectations["should_not_recall_ids"])

    governed_ids = tri_answer_contract_evidence_ids(case)

    assert governed_ids == tuple(item_id for item_id in tri_ids if item_id not in forbidden)
    assert set(case.expectations["should_recall_ids"]) <= set(governed_ids)


def test_contract_extracts_answer_terms_without_raw_prompt_or_full_answer() -> None:
    case = _case_with_should_not_in_tri()

    contract = build_tri_answer_contract(case)

    answer_expectations = case.expectations["answer_expectations"]
    expected_terms = answer_expectations.get("expected_answer_contains", ())
    expected_term_groups = answer_expectations.get("expected_answer_contains_any", ())
    forbidden_terms = answer_expectations.get("forbidden_answer_contains", ())

    assert set(contract.required_terms) >= {str(term) for term in expected_terms}
    assert contract.required_terms
    assert contract.required_term_groups == tuple(
        tuple(str(term) for term in group) for group in expected_term_groups
    )
    assert contract.forbidden_terms == tuple(str(term) for term in forbidden_terms)
    assert contract.raw_answer == ""
    assert contract.raw_prompt == ""


def test_rendered_contract_is_structured_and_private() -> None:
    case = _case_with_should_not_in_tri()
    contract = build_tri_answer_contract(case)

    text = render_answer_contract_block(contract)

    assert "Answer Contract" in text
    assert "must_use_memory_ids" in text
    assert "forbidden_memory_ids" in text
    assert "required_terms" in text
    assert "不要使用 forbidden_memory_ids" in text
    assert "memory_id=" in text
    assert case.setup["query"] not in text


def test_governed_contract_uses_supplied_allowed_ids_and_marks_dropped_tri_ids() -> None:
    case = _case_with_should_not_in_tri()
    base_contract = build_tri_answer_contract(case)
    governed_ids = tuple(
        item_id
        for item_id in base_contract.allowed_evidence_ids
        if item_id in set(str(item) for item in case.expectations["should_recall_ids"])
    )

    contract = build_governed_tri_answer_contract(case, governed_ids)

    assert contract.profile_name == "chain_tri_governed_answer_contract"
    assert contract.allowed_evidence_ids == governed_ids
    assert set(contract.must_use_ids) == set(
        str(item) for item in case.expectations["should_recall_ids"]
    )
    assert set(contract.forbidden_ids) == (
        set(base_contract.tri_ids)
        & set(str(item) for item in case.expectations["should_not_recall_ids"])
    )
    assert set(contract.governance_dropped_ids) == (
        set(base_contract.tri_ids) - set(governed_ids) - set(contract.forbidden_ids)
    )
    assert set(contract.forbidden_ids).isdisjoint(contract.allowed_evidence_ids)
    assert set(contract.governance_dropped_ids).isdisjoint(contract.allowed_evidence_ids)


def test_governed_contract_evidence_ids_preserve_governed_order_and_tri_membership() -> None:
    case = _case_with_should_not_in_tri()
    base_contract = build_tri_answer_contract(case)
    governed_ids = tuple(reversed(base_contract.allowed_evidence_ids))
    expected_ids = set(str(item) for item in case.expectations["should_recall_ids"])

    ids = tri_governed_answer_contract_evidence_ids(case, governed_ids)

    assert ids == tuple(
        item_id
        for item_id in governed_ids
        if item_id in set(base_contract.tri_ids)
        and item_id not in set(base_contract.forbidden_ids)
    )
    assert expected_ids <= set(ids)


def test_render_governed_contract_uses_profile_name() -> None:
    case = _case_with_should_not_in_tri()
    contract = build_governed_tri_answer_contract(
        case,
        build_tri_answer_contract(case).allowed_evidence_ids,
    )

    text = render_answer_contract_block(contract)

    assert "Answer Contract: chain_tri_governed_answer_contract" in text
    assert "must_use_memory_ids" in text
    assert "governance_dropped_memory_ids" in text
    assert "allowed_evidence:" in text


def test_production_governed_contract_uses_tiered_metadata_not_answer_expectations() -> None:
    case = _case_with_should_not_in_tri()
    governed_trace_info = {
        "ids": ("target", "weak", "conflict", "gap"),
        "trace": {
            "candidate_governance_mode": "tiered",
            "candidate_risk_tiers": [
                {
                    "candidate_id": "target",
                    "tier": "allow",
                    "risks": (),
                    "lane": "semantic",
                },
                {
                    "candidate_id": "weak",
                    "tier": "downgrade",
                    "risks": ("weak_source_ref",),
                    "lane": "semantic",
                },
                {
                    "candidate_id": "conflict",
                    "tier": "requires_review",
                    "risks": ("conflict_candidate",),
                    "lane": "semantic",
                },
                {
                    "candidate_id": "gap",
                    "tier": "requires_review",
                    "risks": ("insufficient_evidence",),
                    "lane": "semantic",
                },
                {
                    "candidate_id": "blocked",
                    "tier": "delete",
                    "risks": ("forbidden_candidate",),
                    "lane": "semantic",
                },
                {
                    "candidate_id": "old",
                    "tier": "delete",
                    "risks": ("superseded_candidate",),
                    "lane": "semantic",
                },
            ],
        },
    }
    case = replace(
        case,
        setup={
            **case.setup,
            "memory_items": [
                {
                    "id": "target",
                    "summary": "active target evidence",
                    "status": "active",
                    "source_ref": "telegram:1:1",
                },
                {
                    "id": "weak",
                    "summary": "weak source evidence",
                    "status": "active",
                    "source_ref": "session:telegram:1",
                },
                {
                    "id": "conflict",
                    "summary": "conflicting evidence",
                    "status": "active",
                    "source_ref": "telegram:1:2",
                    "conflict": True,
                },
                {
                    "id": "gap",
                    "summary": "insufficient evidence",
                    "status": "active",
                    "source_ref": "telegram:1:3",
                    "insufficient_evidence": True,
                },
                {
                    "id": "blocked",
                    "summary": "blocked evidence",
                    "status": "active",
                    "source_ref": "telegram:1:4",
                    "forbidden": True,
                },
                {
                    "id": "old",
                    "summary": "old superseded evidence",
                    "status": "superseded",
                    "source_ref": "telegram:1:5",
                },
            ],
        },
        expectations={
            **case.expectations,
            "answer_expectations": {
                "expected_answer_contains": ["ORACLE_TERM"],
                "expected_answer_contains_any": [["ORACLE_GROUP"]],
                "forbidden_answer_contains": ["ORACLE_FORBIDDEN"],
            },
        },
    )

    contract = build_production_governed_tri_evidence_contract(
        case,
        governed_trace_info,
    )

    assert contract.profile_name == "chain_tri_governed_answer_contract"
    assert contract.production_safe is True
    assert contract.uses_fixture_answer_expectations is False
    assert contract.allowed_evidence == ("target", "weak", "conflict", "gap")
    assert contract.likely_relevant_evidence == ("target", "weak")
    assert contract.stale_warning == ("old",)
    assert contract.conflict_warning == ("conflict",)
    assert contract.active_version == ("target", "weak", "conflict", "gap")
    assert contract.forbidden_boundary == ("blocked",)
    assert contract.allowed_evidence_ids == ("target", "weak", "conflict", "gap")
    assert contract.likely_relevant_evidence_ids == ("target", "weak")
    assert contract.downgrade_ids == ("weak",)
    assert contract.requires_review_ids == ("conflict", "gap")
    assert contract.conflict_warning_ids == ("conflict",)
    assert contract.insufficient_evidence_ids == ("gap",)
    assert contract.insufficient_evidence_fallback is True
    assert contract.forbidden_boundary_ids == ("blocked",)
    assert contract.stale_warning_ids == ("old",)
    assert contract.active_version_ids == ("target", "weak", "conflict", "gap")
    assert contract.required_terms == ()
    assert contract.required_term_groups == ()
    assert contract.forbidden_terms == ()


def test_render_production_evidence_contract_is_structured_and_not_oracle_terms() -> None:
    case = _case_with_should_not_in_tri()
    case = replace(
        case,
        expectations={
            **case.expectations,
            "answer_expectations": {
                "expected_answer_contains": ["ORACLE_TERM"],
                "expected_answer_contains_any": [["ORACLE_GROUP"]],
                "forbidden_answer_contains": ["ORACLE_FORBIDDEN"],
            },
        },
    )
    contract = build_production_governed_tri_evidence_contract(
        case,
        {
            "ids": build_tri_answer_contract(case).allowed_evidence_ids,
            "trace": {"candidate_governance_mode": "tiered", "candidate_risk_tiers": []},
        },
    )

    text = render_production_evidence_contract_block(contract)

    assert "Evidence Contract: chain_tri_governed_answer_contract" in text
    assert "production_safe=true" in text
    assert "allowed_evidence:" in text
    assert "likely_relevant_evidence_ids:" in text
    assert "stale_warning_ids:" in text
    assert "conflict_warning_ids:" in text
    assert "active_version_ids:" in text
    assert "insufficient_evidence_fallback:" in text
    assert "forbidden_boundary_ids:" in text
    assert "required_terms:" not in text
    assert "required_term_groups:" not in text
    assert "forbidden_terms:" not in text
    assert "ORACLE_TERM" not in text
    assert "ORACLE_GROUP" not in text
    assert "ORACLE_FORBIDDEN" not in text
    assert case.setup["query"] not in text
