from memory2.version_chain_experiments import build_version_chain_shadow_result


def test_version_chain_detects_active_leaf_and_stale_recall() -> None:
    result = build_version_chain_shadow_result(
        memory_items=[
            {"id": "old", "status": "superseded", "summary": "用户喜欢英文"},
            {"id": "new", "status": "active", "summary": "用户喜欢中文"},
        ],
        replacements=[
            {
                "old_item_id": "old",
                "old_summary": "用户喜欢英文",
                "new_item_id": "new",
                "new_summary": "用户喜欢中文",
                "relation_type": "supersede",
                "source_ref": "cli:local@post_response",
            }
        ],
        recalled_items=[{"id": "old", "status": "superseded"}],
    )

    assert result.experimental_result["chain_count"] == 1
    assert result.experimental_result["active_leaf_ids"] == ["new"]
    assert result.metrics["max_chain_depth"] == 2
    assert result.metrics["stale_recalled_count"] == 1
    assert result.metrics["rollback_candidate_count"] == 1


def test_version_chain_detects_conflict_chain_with_multiple_active_leaves() -> None:
    result = build_version_chain_shadow_result(
        memory_items=[
            {"id": "root", "status": "superseded", "summary": "规则 v1"},
            {"id": "left", "status": "active", "summary": "规则 v2"},
            {"id": "right", "status": "active", "summary": "规则 v2 冲突"},
        ],
        replacements=[
            {
                "old_item_id": "root",
                "new_item_id": "left",
                "relation_type": "supersede",
            },
            {
                "old_item_id": "root",
                "new_item_id": "right",
                "relation_type": "supersede",
            },
        ],
        recalled_items=[{"id": "left", "status": "active"}],
    )

    assert result.experimental_result["chain_count"] == 1
    assert set(result.experimental_result["active_leaf_ids"]) == {"left", "right"}
    assert result.metrics["conflict_chain_count"] == 1
    assert result.metrics["active_leaf_count"] == 2


def test_version_chain_ignores_standalone_active_items() -> None:
    result = build_version_chain_shadow_result(
        memory_items=[
            {"id": "standalone", "status": "active", "summary": "普通记忆"},
            {"id": "old", "status": "superseded", "summary": "旧规则"},
            {"id": "new", "status": "active", "summary": "新规则"},
        ],
        replacements=[
            {"old_item_id": "old", "new_item_id": "new", "relation_type": "supersede"}
        ],
        recalled_items=[{"id": "standalone", "status": "active"}],
    )

    assert result.experimental_result["chain_count"] == 1
    assert result.experimental_result["active_leaf_ids"] == ["new"]
    assert result.metrics["stale_recalled_count"] == 0


def test_version_chain_uses_recalled_item_status_when_snapshot_is_incomplete() -> None:
    result = build_version_chain_shadow_result(
        memory_items=[],
        replacements=[],
        recalled_items=[{"id": "active_from_baseline", "status": "active"}],
    )

    assert result.metrics["stale_recalled_count"] == 0
