from memory2.provenance_experiments import (
    build_provenance_shadow_result,
    parse_source_ref,
)


def test_parse_source_ref_supports_message_id_json_and_hash_suffix() -> None:
    parsed = parse_source_ref('["tg:1:2","tg:1:3"]#h:abc123')

    assert parsed["parse_ok"] is True
    assert parsed["level"] == "message"
    assert parsed["message_ids"] == ["tg:1:2", "tg:1:3"]
    assert parsed["span_or_suffix"] == "h:abc123"


def test_parse_source_ref_supports_post_response_session_ref() -> None:
    parsed = parse_source_ref("cli:local@post_response")

    assert parsed["parse_ok"] is True
    assert parsed["level"] == "session"
    assert parsed["session_key"] == "cli:local"


def test_provenance_shadow_counts_coverage_orphans_and_cross_scope_risk() -> None:
    result = build_provenance_shadow_result(
        memory_items=[
            {
                "id": "scoped",
                "source_ref": '["cli:local:1"]#profile',
                "scope_channel": "cli",
                "scope_chat_id": "local",
            },
            {
                "id": "orphan",
                "source_ref": "",
                "scope_channel": "",
                "scope_chat_id": "",
            },
            {
                "id": "cross",
                "source_ref": "telegram:1@post_response",
                "scope_channel": "telegram",
                "scope_chat_id": "1",
            },
        ],
        recalled_items=[{"id": "scoped"}, {"id": "cross"}],
        scope_channel="cli",
        scope_chat_id="local",
    )

    assert result.metrics["source_ref_coverage"] == 0.6667
    assert result.metrics["parse_success_rate"] == 1.0
    assert result.metrics["orphan_memory_count"] == 1
    assert result.metrics["cross_scope_risk_count"] == 1
    assert result.metrics["cross_scope_memory_count"] == 1
    assert result.metrics["message_level_source_count"] == 1


def test_provenance_shadow_cross_scope_risk_is_recall_scoped() -> None:
    result = build_provenance_shadow_result(
        memory_items=[
            {
                "id": "cross_not_recalled",
                "source_ref": "telegram:1@post_response",
                "scope_channel": "telegram",
                "scope_chat_id": "1",
            }
        ],
        recalled_items=[],
        scope_channel="cli",
        scope_chat_id="local",
    )

    assert result.metrics["cross_scope_memory_count"] == 1
    assert result.metrics["cross_scope_risk_count"] == 0
