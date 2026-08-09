from __future__ import annotations

import json
from pathlib import Path

from miniroute.tools.generate_v3_dataset import build_v3_records, split_v3_records
from miniroute.tools.validate_dataset import validate_dataset_files


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_v3_adds_boundary_hard_negative_sources() -> None:
    records = build_v3_records()
    sources = {record.source for record in records}

    assert "v3:status_query_vs_tool_execution" in sources
    assert "v3:file_read_vs_tool_execution" in sources
    assert "v3:content_save_vs_tool_execution" in sources
    assert "v3:chat_memory_profile_hard_negative" in sources
    assert "v3:profile_memory_content_boundary" in sources
    assert "v3:unknown_tools_vs_shell_tools" in sources


def test_v3_boundary_labels_target_observed_confusions() -> None:
    records = build_v3_records()
    by_source = {}
    for record in records:
        by_source.setdefault(record.source, []).append(record)

    assert all(
        record.label.intent == "status_query"
        and record.label.tool_scope == ["observe_tools"]
        and record.label.risk_level == "read_only"
        for record in by_source["v3:status_query_vs_tool_execution"]
    )
    assert all(
        record.label.intent == "file_read"
        and record.label.tool_scope == ["file_read_tools"]
        and record.label.risk_level == "read_only"
        for record in by_source["v3:file_read_vs_tool_execution"]
    )
    assert all(
        record.label.intent == "content_save"
        and record.label.tool_scope == ["content_tools"]
        and record.label.risk_level == "write"
        for record in by_source["v3:content_save_vs_tool_execution"]
    )
    assert all(
        record.label.intent == "chat"
        and record.label.need_tools is False
        and record.label.tool_scope == ["none"]
        and record.label.risk_level == "none"
        for record in by_source["v3:chat_memory_profile_hard_negative"]
    )
    assert all(
        record.label.intent == "tool_execution"
        and record.label.tool_scope == ["unknown_tools"]
        for record in by_source["v3:unknown_tools_vs_shell_tools"]
    )


def test_v3_splits_and_validator_accept_generated_dataset(tmp_path: Path) -> None:
    splits = split_v3_records(build_v3_records())
    paths = {
        "train": tmp_path / "route_v3_train.jsonl",
        "valid": tmp_path / "route_v3_valid.jsonl",
        "test": tmp_path / "route_v3_test.jsonl",
    }
    _write_jsonl(paths["train"], [record.to_training_json() for record in splits.train])
    _write_jsonl(paths["valid"], [record.to_training_json() for record in splits.valid])
    _write_jsonl(paths["test"], [record.to_training_json() for record in splits.test])

    report = validate_dataset_files(paths)

    assert len(splits.train) > 1061
    assert len(splits.valid) > 227
    assert len(splits.test) > 232
    assert report.ok is True
    assert report.high_risk_test_count >= 30
    assert report.issues == []
