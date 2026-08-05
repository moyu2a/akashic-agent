from __future__ import annotations

import json
from pathlib import Path

from miniroute.evaluation.evaluate import evaluate_predictions
from miniroute.tools.generate_v1_dataset import build_v1_records, split_v1_records
from miniroute.tools.validate_dataset import validate_dataset_files
from miniroute.v1_schema import (
    INTENTS,
    RISK_LEVELS,
    TOOL_SCOPES,
    RouteLabel,
    parse_training_record,
)


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def test_route_label_accepts_v1_schema() -> None:
    label = RouteLabel(
        intent="memory_query",
        need_memory=True,
        need_tools=False,
        tool_scope=["memory_tools"],
        risk_level="read_only",
    )

    assert label.intent in INTENTS
    assert label.tool_scope == ["memory_tools"]
    assert "high_risk" in RISK_LEVELS
    assert "shell_tools" in TOOL_SCOPES


def test_parse_training_record_rejects_unknown_label() -> None:
    record = {
        "conversations": [
            {
                "role": "user",
                "content": "判断用户请求的意图，并只输出 JSON。\n\n用户请求：帮我看看 README。",
            },
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "intent": "unknown",
                        "need_memory": False,
                        "need_tools": True,
                        "tool_scope": ["file_read_tools"],
                        "risk_level": "read_only",
                    },
                    ensure_ascii=False,
                ),
            },
        ]
    }

    errors = parse_training_record(record, source="unit").errors

    assert any("unknown intent" in error for error in errors)


def test_training_record_exports_minimind_conversations_format() -> None:
    record = build_v1_records()[0].to_training_json()

    assert list(record) == ["conversations"]
    assert record["conversations"][0]["role"] == "user"
    assert record["conversations"][1]["role"] == "assistant"
    assert "用户请求：" in record["conversations"][0]["content"]
    assistant = json.loads(record["conversations"][1]["content"])
    assert assistant == {
        "intent": "chat",
        "need_memory": False,
        "need_tools": False,
        "tool_scope": ["none"],
        "risk_level": "none",
    }


def test_v1_generator_produces_required_distribution() -> None:
    records = build_v1_records()
    splits = split_v1_records(records)

    assert len(splits.train) >= 800
    assert len(splits.valid) >= 100
    assert len(splits.test) >= 150

    train_intents = {record.label.intent for record in splits.train}
    assert train_intents == set(INTENTS)

    high_risk_test_count = sum(
        1 for record in splits.test if record.label.risk_level == "high_risk"
    )
    assert high_risk_test_count >= 30


def test_dataset_validator_accepts_generated_files(tmp_path: Path) -> None:
    records = build_v1_records()
    splits = split_v1_records(records)
    train = [record.to_training_json() for record in splits.train]
    valid = [record.to_training_json() for record in splits.valid]
    test = [record.to_training_json() for record in splits.test]
    paths = {
        "train": tmp_path / "route_train.jsonl",
        "valid": tmp_path / "route_valid.jsonl",
        "test": tmp_path / "route_test.jsonl",
    }
    _write_jsonl(paths["train"], train)
    _write_jsonl(paths["valid"], valid)
    _write_jsonl(paths["test"], test)

    report = validate_dataset_files(paths)

    assert report.ok is True
    assert report.total_records == len(train) + len(valid) + len(test)
    assert report.high_risk_test_count >= 30


def test_evaluator_reports_metrics_and_scope_overopen() -> None:
    expected = [
        RouteLabel(
            intent="chat",
            need_memory=False,
            need_tools=False,
            tool_scope=["none"],
            risk_level="none",
        ),
        RouteLabel(
            intent="tool_execution",
            need_memory=False,
            need_tools=True,
            tool_scope=["shell_tools"],
            risk_level="high_risk",
        ),
    ]
    predicted = [
        RouteLabel(
            intent="chat",
            need_memory=False,
            need_tools=False,
            tool_scope=["none"],
            risk_level="none",
        ),
        RouteLabel(
            intent="tool_execution",
            need_memory=False,
            need_tools=True,
            tool_scope=["file_read_tools"],
            risk_level="read_only",
        ),
    ]

    report = evaluate_predictions(expected, predicted)

    assert report.total == 2
    assert report.intent_accuracy == 100.0
    assert report.risk_level_accuracy == 50.0
    assert report.high_risk_recall == 0.0
    assert report.risk_underestimate_count == 1
