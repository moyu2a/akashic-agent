from __future__ import annotations

from memory2.eval_answer_contract import (
    build_tri_answer_contract,
    render_answer_contract_block,
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
