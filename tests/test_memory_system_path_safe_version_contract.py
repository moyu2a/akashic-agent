from __future__ import annotations

from memory2.system_path_safe_version_contract import (
    build_system_path_safe_version_contract,
    render_system_path_evidence_contract_block,
    system_path_contract_to_dict,
)


def _item(
    item_id: str,
    summary: str,
    *,
    status: str = "active",
    source_ref: str = "telegram:1:1",
    extra_json: dict[str, object] | None = None,
    **extra: object,
) -> dict[str, object]:
    return {
        "id": item_id,
        "summary": summary,
        "memory_type": "preference",
        "status": status,
        "source_ref": source_ref,
        "extra_json": extra_json or {},
        **extra,
    }


def test_system_path_contract_uses_tiered_governance_without_fixture_ids() -> None:
    result = build_system_path_safe_version_contract(
        query="我现在默认用什么测试框架？",
        baseline_items=[
            _item("m-current", "用户偏好使用 pytest。"),
            _item("m-forbidden", "用户禁止使用 nose。", forbidden=True),
        ],
        route_trace={
            "candidates_by_lane": {
                "semantic": [
                    _item("m-current", "用户偏好使用 pytest。"),
                    _item("m-forbidden", "用户禁止使用 nose。", forbidden=True),
                ],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
    )

    assert result.contract.production_safe is True
    assert result.contract.uses_fixture_answer_expectations is False
    assert result.contract.allowed_evidence_ids == ("m-current",)
    assert result.contract.forbidden_boundary_ids == ("m-forbidden",)
    assert result.contract.deleted_evidence_ids == ("m-forbidden",)
    assert result.contract.candidate_risk_tier_counts["delete"] == 1
    assert result.contract.accepted_candidate_risk_tier_counts["allow"] == 1


def test_system_path_render_hides_raw_forbidden_and_deleted_ids() -> None:
    result = build_system_path_safe_version_contract(
        query="测试偏好是什么？",
        baseline_items=[_item("m-current", "用户偏好使用 pytest。")],
        route_trace={
            "candidates_by_lane": {
                "semantic": [
                    _item("m-current", "用户偏好使用 pytest。"),
                    _item("blocked-id", "禁止使用 nose。", forbidden=True),
                ],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
    )

    text = render_system_path_evidence_contract_block(result.contract)

    assert "Evidence Contract: system_memory_safe_version_governed" in text
    assert "allowed_evidence:" in text
    assert "用户偏好使用 pytest。" in text
    assert "forbidden_boundary_count: 1" in text
    assert "deleted_evidence_count: 1" in text
    assert "forbidden_boundary_ids:" not in text
    assert "deleted_evidence_ids:" not in text
    assert "likely_relevant_evidence_ids:" not in text
    assert "active_version_ids:" not in text
    assert "blocked-id" not in text
    assert "m-current" not in text


def test_system_path_contract_dict_is_private_but_auditable() -> None:
    result = build_system_path_safe_version_contract(
        query="测试偏好是什么？",
        baseline_items=[_item("m-current", "用户偏好使用 pytest。")],
        route_trace={
            "candidates_by_lane": {
                "semantic": [_item("m-current", "用户偏好使用 pytest。")],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
    )

    payload = system_path_contract_to_dict(result.contract)

    assert payload["production_safe"] is True
    assert payload["production_safe_evidence_contract"] is True
    assert payload["uses_fixture_answer_expectations"] is False
    assert payload["allowed_evidence_ids"] == ["m-current"]
    assert "raw_prompt" not in payload
    assert "raw_answer" not in payload


def test_system_path_contract_enforces_replacement_version_boundary() -> None:
    old_item = _item(
        "m-old",
        "用户旧偏好使用 nose。",
        status="superseded",
        source_ref="telegram:1:old",
    )
    current_item = _item(
        "m-current",
        "用户当前偏好使用 pytest。",
        status="active",
        source_ref="telegram:1:new",
    )

    result = build_system_path_safe_version_contract(
        query="我现在默认用什么测试框架？",
        baseline_items=[old_item, current_item],
        route_trace={
            "candidates_by_lane": {
                "semantic": [old_item, current_item],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[
            {
                "old_item_id": "m-old",
                "new_item_id": "m-current",
                "old_memory_type": "preference",
                "new_memory_type": "preference",
                "old_summary": "用户旧偏好使用 nose。",
                "new_summary": "用户当前偏好使用 pytest。",
                "old_source_ref": "telegram:1:old",
                "new_source_ref": "telegram:1:new",
            }
        ],
        top_k=8,
    )

    text = render_system_path_evidence_contract_block(result.contract)

    assert result.contract.allowed_evidence_ids == ("m-current",)
    assert result.contract.active_version_ids == ("m-current",)
    assert result.contract.stale_warning_ids == ("m-old",)
    assert result.contract.deleted_evidence_ids == ("m-old",)
    assert result.contract.version_boundary["replacement_count"] == 1
    assert result.contract.version_boundary["stale_recalled_count"] == 0
    assert "m-old" not in text
    assert "用户旧偏好使用 nose。" not in text


def test_system_path_contract_retains_downgrade_and_requires_review_candidates() -> None:
    downgrade = _item(
        "m-downgrade",
        "用户可能偏好 pytest。",
        source_ref="telegram:1@post_response",
    )
    requires_review = _item(
        "m-review",
        "用户偏好测试工具存在冲突，需要复核。",
        source_ref="telegram:1:2",
        conflict=True,
    )

    result = build_system_path_safe_version_contract(
        query="我默认用什么测试框架？",
        baseline_items=[downgrade, requires_review],
        route_trace={
            "candidates_by_lane": {
                "semantic": [downgrade, requires_review],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
    )

    assert result.contract.allowed_evidence_ids == ("m-downgrade", "m-review")
    assert result.contract.downgrade_ids == ("m-downgrade",)
    assert result.contract.requires_review_ids == ("m-review",)
    assert result.contract.candidate_risk_tier_counts["downgrade"] == 1
    assert result.contract.candidate_risk_tier_counts["requires_review"] == 1
    assert result.contract.accepted_candidate_risk_tier_counts["downgrade"] == 1
    assert result.contract.accepted_candidate_risk_tier_counts["requires_review"] == 1
