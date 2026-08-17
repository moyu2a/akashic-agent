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


def test_system_path_answer_guidance_is_default_off() -> None:
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

    assert "Answer Guidance:" not in result.text_block
    assert system_path_contract_to_dict(result.contract)["answer_guidance_enabled"] is False


def test_system_path_answer_guidance_is_production_safe_and_private() -> None:
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
        answer_guidance_enabled=True,
    )

    text = result.text_block
    payload = system_path_contract_to_dict(
        result.contract,
        answer_guidance_enabled=True,
    )

    assert "Answer Guidance:" in text
    assert "Use allowed_evidence as the only source for the answer." in text
    assert "State concrete facts from allowed_evidence directly." in text
    assert "same language as the current user question" in text
    assert "use all salient user-specific evidence" in text
    assert "blocked-id" not in text


def test_guided_retry_shadow_tells_model_not_to_repeat_old_values() -> None:
    old_item = _item(
        "style-old",
        "用户旧回答风格偏好是长段落。",
        status="superseded",
        source_ref="session:old",
    )
    current_item = _item(
        "style-current",
        "用户当前回答风格偏好是短句和要点。",
        status="active",
        source_ref="session:new",
    )
    result = build_system_path_safe_version_contract(
        query="我现在的回答风格偏好是什么？",
        baseline_items=[old_item, current_item],
        route_trace={
            "candidates_by_lane": {
                "semantic": [current_item, old_item],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[
            {
                "old_item_id": "style-old",
                "old_summary": "用户旧回答风格偏好是长段落。",
                "new_item_id": "style-current",
                "new_summary": "用户当前回答风格偏好是短句和要点。",
                "relation_type": "supersede",
            }
        ],
        answer_guidance_enabled=True,
        answer_prompt_variant="guided_retry_shadow",
    )

    text = render_system_path_evidence_contract_block(
        result.contract,
        answer_guidance_enabled=True,
        answer_prompt_variant="guided_retry_shadow",
    )

    assert "Only state the current truth" in text
    assert "Do not repeat old, stale, or superseded values verbatim" in text
    assert "Normally do not mention replacement history" in text
    assert "If the user explicitly asks about old preferences" in text
    assert "旧版本已失效" in text


def test_answer_candidate_contract_extracts_current_truth_and_counts() -> None:
    current = _item("m-current", "用户当前默认测试框架是 pytest。")
    old = _item("m-old", "用户旧测试框架是 nose。", status="superseded")

    result = build_system_path_safe_version_contract(
        query="我现在默认用什么测试框架？",
        baseline_items=[old, current],
        route_trace={
            "candidates_by_lane": {
                "semantic": [old, current],
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
                "old_summary": "用户旧测试框架是 nose。",
                "new_summary": "用户当前默认测试框架是 pytest。",
                "old_source_ref": "telegram:1:old",
                "new_source_ref": "telegram:1:new",
            }
        ],
        top_k=8,
        answer_guidance_enabled=True,
        answer_prompt_variant="guided_retry_shadow",
    )

    candidate = result.contract.answer_candidate_contract
    assert candidate.enabled is True
    assert candidate.current_truth_ids == ("m-current",)
    assert candidate.current_truth_lines == ("用户当前默认测试框架是 pytest。",)
    assert candidate.must_include_term_count == 1
    assert candidate.forbidden_old_value_ids == ("m-old",)
    assert candidate.language_requirement == "match_user_language"
    assert candidate.candidate_reason == "safe_version_guided_retry_shadow"


def test_guided_retry_shadow_renders_prompt_contract_with_safe_report_counts() -> None:
    result = build_system_path_safe_version_contract(
        query="测试偏好是什么？",
        baseline_items=[
            _item("m-current", "用户当前偏好使用 pytest。"),
            _item("m-old", "用户旧偏好使用 nose。", status="superseded"),
        ],
        route_trace={
            "candidates_by_lane": {
                "semantic": [
                    _item("m-current", "用户当前偏好使用 pytest。"),
                    _item("m-old", "用户旧偏好使用 nose。", status="superseded"),
                ],
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
        answer_guidance_enabled=True,
        answer_prompt_variant="guided_retry_shadow",
    )

    text = result.text_block
    payload = system_path_contract_to_dict(
        result.contract,
        answer_guidance_enabled=True,
    )

    assert "Answer Candidate Contract:" in text
    assert "current_truth:" in text
    assert "Directly answer the user's question first." in text
    assert "Restate at least one concrete current_truth fact in the answer." in text
    assert "Do not answer with only an acknowledgement" in text
    assert "Do not output code blocks" in text
    assert "must_include_term_count: 1" in text
    assert "用户当前偏好使用 pytest。" in text
    assert "m-current" not in text
    assert "m-old" not in text
    assert payload["answer_candidate_contract"]["enabled"] is True
    assert payload["answer_candidate_contract"]["current_truth_count"] == 1
    assert payload["answer_candidate_contract"]["must_include_term_count"] == 1
    assert "current_truth_lines" not in payload["answer_candidate_contract"]
    assert "must_include_terms" not in payload["answer_candidate_contract"]
    assert "raw_prompt" not in payload
    assert "raw_answer" not in payload
    assert "forbidden_boundary_ids:" not in text
    assert "deleted_evidence_ids:" not in text
    assert payload["answer_guidance_enabled"] is True
    assert payload["uses_fixture_answer_expectations"] is False


def test_schema_first_shadow_renders_structured_selection_then_natural_answer() -> None:
    result = build_system_path_safe_version_contract(
        query="测试偏好是什么？",
        baseline_items=[
            _item("m-current", "用户当前偏好使用 pytest。"),
            _item("m-old", "用户旧偏好使用 nose。", status="superseded"),
        ],
        route_trace={
            "candidates_by_lane": {
                "semantic": [
                    _item("m-current", "用户当前偏好使用 pytest。"),
                    _item("m-old", "用户旧偏好使用 nose。", status="superseded"),
                ],
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
        answer_guidance_enabled=True,
        answer_prompt_variant="schema_first_shadow",
    )

    text = result.text_block
    payload = system_path_contract_to_dict(
        result.contract,
        answer_guidance_enabled=True,
    )

    assert payload["answer_prompt_variant"] == "schema_first_shadow"
    assert payload["answer_candidate_contract"]["enabled"] is True
    assert (
        payload["answer_candidate_contract"]["candidate_reason"]
        == "safe_version_schema_first_shadow"
    )
    assert payload["answer_candidate_contract"]["current_truth_count"] == 1
    assert payload["answer_candidate_contract"]["must_include_term_count"] == 1
    assert "must_include_terms" not in payload["answer_candidate_contract"]
    assert "Schema-First Answer Shadow:" in text
    assert "First select the answer facts internally" in text
    assert "Then write only the final natural-language answer" in text
    assert "selected_facts" in text
    assert "ignored_superseded_or_stale" in text
    assert "Do not expose JSON" in text
    assert "用户当前偏好使用 pytest。" in text
    assert "m-current" not in text
    assert "m-old" not in text


def test_guided_retry_shadow_marks_contract_retrieval_complete_when_answerable() -> None:
    result = build_system_path_safe_version_contract(
        query="上次那个回答方式怎么说？",
        baseline_items=[_item("m-current", "用户偏好中文回答。")],
        route_trace={
            "candidates_by_lane": {
                "semantic": [_item("m-current", "用户偏好中文回答。")],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
        answer_guidance_enabled=True,
        answer_prompt_variant="guided_retry_shadow",
    )

    text = result.text_block
    assert "retrieval and governance for this turn are already complete" in text
    assert "insufficient_evidence_fallback=false" in text
    assert "Do not restart recall, search, fetch, or read memory files" in text
    assert "Do not output pseudo tool calls, DSML markup" in text
    assert "Do not answer with \"先查\", \"先翻\", or \"核实\"" in text
    assert "用户偏好中文回答。" in text


def test_schema_first_shadow_marks_contract_retrieval_complete_when_answerable() -> None:
    result = build_system_path_safe_version_contract(
        query="那个旧方案怎么回滚？",
        baseline_items=[_item("m-current", "版本链只保留当前叶子并记录回滚候选。")],
        route_trace={
            "candidates_by_lane": {
                "semantic": [_item("m-current", "版本链只保留当前叶子并记录回滚候选。")],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
        answer_guidance_enabled=True,
        answer_prompt_variant="schema_first_shadow",
    )

    text = result.text_block
    assert "retrieval and governance for this turn are already complete" in text
    assert "Do not restart recall, search, fetch, or read memory files" in text
    assert "Then write only the final natural-language answer" in text


def test_guided_retry_shadow_does_not_mark_retrieval_complete_when_insufficient() -> None:
    result = build_system_path_safe_version_contract(
        query="这个有没有证据？",
        baseline_items=[],
        route_trace={
            "candidates_by_lane": {
                "semantic": [],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
        answer_guidance_enabled=True,
        answer_prompt_variant="guided_retry_shadow",
    )

    assert result.contract.insufficient_evidence_fallback is True
    assert (
        "retrieval and governance for this turn are already complete"
        not in result.text_block
    )


def test_system_path_structured_guided_variant_groups_answer_critical_evidence() -> None:
    result = build_system_path_safe_version_contract(
        query="测试偏好是什么？",
        baseline_items=[
            _item("m-current", "用户偏好使用 pytest。"),
            _item("blocked-id", "禁止使用 nose。", forbidden=True),
        ],
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
        answer_prompt_variant="structured_guided",
    )

    text = result.text_block
    payload = system_path_contract_to_dict(result.contract)

    assert "Structured Answer Guidance:" in text
    assert "answer_critical_evidence:" in text
    assert "用户偏好使用 pytest。" in text
    assert "禁止使用 nose。" not in text
    assert "active_allowed_evidence_count: 1" in text
    assert "Use answer_critical_evidence first." in text
    assert payload["answer_guidance_enabled"] is True
    assert payload["answer_prompt_variant"] == "structured_guided"
    assert "m-current" not in text
    assert "blocked-id" not in text


def test_system_path_near_query_variant_marks_next_user_message_scope() -> None:
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
        answer_prompt_variant="near_query_block",
    )

    text = result.text_block
    assert "Question-Proximal Memory Evidence:" in text
    assert "Use this block for the immediately following user request." in text
    assert (
        "Do not use deleted, superseded, cross-scope, or forbidden boundary evidence."
        in text
    )
    assert (
        system_path_contract_to_dict(result.contract)["answer_prompt_variant"]
        == "near_query_block"
    )


def test_system_path_standard_variant_keeps_p6o17_baseline_text() -> None:
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
        answer_prompt_variant="standard",
    )

    assert "Answer Guidance:" not in result.text_block
    assert "Structured Answer Guidance:" not in result.text_block
    assert "Question-Proximal Memory Evidence:" not in result.text_block
    assert system_path_contract_to_dict(result.contract)["answer_prompt_variant"] == "standard"
