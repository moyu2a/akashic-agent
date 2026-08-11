from __future__ import annotations

import json
from pathlib import Path

from miniroute.tools.generate_v2_dataset import build_v2_records, split_v2_records
from miniroute.tools.validate_dataset import validate_dataset_files
from miniroute.v1_schema import ROUTE_PROMPT_V2, TOOL_SCOPES


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_v2_schema_adds_unknown_tools_and_enumerated_prompt() -> None:
    assert "unknown_tools" in TOOL_SCOPES
    assert "<think>" not in ROUTE_PROMPT_V2
    for intent in (
        "chat",
        "memory_query",
        "profile_update",
        "task_plan",
        "content_save",
        "file_read",
        "tool_execution",
        "status_query",
    ):
        assert intent in ROUTE_PROMPT_V2
    for scope in (
        "none",
        "memory_tools",
        "task_tools",
        "content_tools",
        "file_read_tools",
        "file_write_tools",
        "shell_tools",
        "observe_tools",
        "unknown_tools",
    ):
        assert scope in ROUTE_PROMPT_V2


def test_v2_memory_records_treat_memory_as_tool_domain() -> None:
    records = build_v2_records()
    memory_records = [
        record for record in records if record.label.intent == "memory_query"
    ]
    profile_records = [
        record for record in records if record.label.intent == "profile_update"
    ]

    assert memory_records
    assert profile_records
    assert all(record.label.need_tools is True for record in memory_records)
    assert all(record.label.tool_scope == ["memory_tools"] for record in memory_records)
    assert all(record.label.need_tools is True for record in profile_records)
    assert all(record.label.tool_scope == ["memory_tools"] for record in profile_records)


def test_v2_contains_unknown_tool_samples() -> None:
    records = build_v2_records()

    unknown_records = [
        record for record in records if record.label.tool_scope == ["unknown_tools"]
    ]

    assert len(unknown_records) >= 40
    assert all(record.label.need_tools is True for record in unknown_records)


def test_v2_splits_are_shuffled_not_grouped_by_intent() -> None:
    splits = split_v2_records(build_v2_records())
    first_twenty_intents = [record.label.intent for record in splits.train[:20]]

    assert len(set(first_twenty_intents)) >= 4
    assert len(splits.train) >= 1000
    assert len(splits.valid) >= 180
    assert len(splits.test) >= 180


def test_v2_validator_accepts_generated_dataset(tmp_path: Path) -> None:
    splits = split_v2_records(build_v2_records())
    paths = {
        "train": tmp_path / "route_v2_train.jsonl",
        "valid": tmp_path / "route_v2_valid.jsonl",
        "test": tmp_path / "route_v2_test.jsonl",
    }
    _write_jsonl(paths["train"], [record.to_training_json() for record in splits.train])
    _write_jsonl(paths["valid"], [record.to_training_json() for record in splits.valid])
    _write_jsonl(paths["test"], [record.to_training_json() for record in splits.test])

    report = validate_dataset_files(paths)

    assert report.ok is True
    assert report.high_risk_test_count >= 30
    assert report.issues == []

