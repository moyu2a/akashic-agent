from __future__ import annotations

import json
from pathlib import Path

import pytest

from miniroute.evaluation.evaluate import evaluate_v4_predictions
from miniroute.tools.generate_v4_dataset import (
    build_v4_records,
    split_v4_records,
    write_v4_dataset_files,
)
from miniroute.tools.validate_dataset import main as validate_dataset_main
from miniroute.tools.validate_dataset import validate_v4_dataset_files
from miniroute.v4_schema import (
    SCENES,
    V4_INSTRUCTION,
    V4RouteLabel,
    V4TrainingRecord,
    parse_v4_training_record,
)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_v4_schema_uses_three_field_scene_protocol() -> None:
    label = V4RouteLabel(scene="task", operation="plan", request_mode="single")

    assert "need_memory" not in label.to_dict()
    assert "tool_scope" not in label.to_dict()
    assert label.to_dict() == {
        "scene": "task",
        "operation": "plan",
        "request_mode": "single",
    }
    assert SCENES == (
        "chat",
        "memory",
        "profile",
        "task",
        "file",
        "status",
        "content",
        "action",
        "unknown",
    )


def test_v4_training_record_input_stays_lightweight() -> None:
    row = V4TrainingRecord(
        input="下一步该做什么？",
        has_active_task=True,
        label=V4RouteLabel("task", "query", "single"),
        source="test:task",
    ).to_training_json()

    user_content = row["conversations"][0]["content"]
    assistant_content = json.loads(row["conversations"][1]["content"])

    assert V4_INSTRUCTION in user_content
    assert "当前状态：has_active_task=true" in user_content
    assert "用户请求：下一步该做什么？" in user_content
    assert "完整记忆：" not in user_content
    assert "工具列表：" not in user_content
    assert assistant_content == {
        "scene": "task",
        "operation": "query",
        "request_mode": "single",
    }


def test_v4_parser_rejects_old_five_field_payload() -> None:
    old_row = {
        "conversations": [
            {"role": "user", "content": f"{V4_INSTRUCTION}\n\n用户请求：帮我解释。"},
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "intent": "chat",
                        "need_memory": False,
                        "need_tools": False,
                        "tool_scope": ["none"],
                        "risk_level": "none",
                    },
                    ensure_ascii=False,
                ),
            },
        ]
    }

    parsed = parse_v4_training_record(old_row)

    assert parsed.ok is False
    assert any("missing field: scene" in issue for issue in parsed.errors)


def test_v4_dataset_covers_all_scenes_and_hard_negative_sources() -> None:
    records = build_v4_records()
    scenes = {record.label.scene for record in records}
    sources = {record.source for record in records}

    assert scenes == set(SCENES)
    assert "v4:chat_vs_profile" in sources
    assert "v4:memory_vs_profile" in sources
    assert "v4:memory_vs_status" in sources
    assert "v4:file_vs_action" in sources
    assert "v4:task_vs_chat" in sources
    assert "v4:content_vs_action" in sources
    assert "v4:unknown_vs_action" in sources
    assert sum(1 for record in records if record.label.request_mode == "compound") >= 600


def test_v4_splits_and_validator_accept_generated_dataset(tmp_path: Path) -> None:
    splits = split_v4_records(build_v4_records())
    paths = {
        "train": tmp_path / "route_v4_train.jsonl",
        "valid": tmp_path / "route_v4_valid.jsonl",
        "test": tmp_path / "route_v4_test.jsonl",
    }
    _write_jsonl(paths["train"], [record.to_training_json() for record in splits.train])
    _write_jsonl(paths["valid"], [record.to_training_json() for record in splits.valid])
    _write_jsonl(paths["test"], [record.to_training_json() for record in splits.test])

    report = validate_v4_dataset_files(paths)

    assert len(splits.train) == 2400
    assert len(splits.valid) == 300
    assert len(splits.test) == 300
    assert report.ok is True
    assert report.total_records == 3000
    assert report.scene_counts["unknown"] <= 240
    assert report.issues == []


def test_v4_validator_cli_supports_schema_v4(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_v4_dataset_files(tmp_path)

    exit_code = validate_dataset_main(
        [
            "--schema",
            "v4",
            "--train",
            str(tmp_path / "route_v4_train.jsonl"),
            "--valid",
            str(tmp_path / "route_v4_valid.jsonl"),
            "--test",
            str(tmp_path / "route_v4_test.jsonl"),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["ok"] is True
    assert output["total_records"] == 3000
    assert "scene_counts" in output
    assert output["compound_count"] >= 600


def test_write_v4_dataset_files_uses_route_v4_names(tmp_path: Path) -> None:
    splits = write_v4_dataset_files(tmp_path)

    assert len(splits.train) == 2400
    assert (tmp_path / "route_v4_train.jsonl").exists()
    assert (tmp_path / "route_v4_valid.jsonl").exists()
    assert (tmp_path / "route_v4_test.jsonl").exists()


def test_v4_evaluation_reports_scene_operation_mode_and_danger_confusions() -> None:
    expected = [
        V4RouteLabel("chat", "answer", "single"),
        V4RouteLabel("action", "execute", "single"),
        V4RouteLabel("file", "read", "single"),
    ]
    predicted = [
        V4RouteLabel("chat", "answer", "single"),
        V4RouteLabel("chat", "answer", "single"),
        V4RouteLabel("action", "execute", "single"),
    ]

    report = evaluate_v4_predictions(expected, predicted)

    assert report.total == 3
    assert report.exact_match_accuracy == pytest.approx(33.3333)
    assert report.scene_accuracy == pytest.approx(33.3333)
    assert report.action_to_chat_count == 1
    assert report.chat_to_action_count == 0
