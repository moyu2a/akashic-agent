from __future__ import annotations

from pathlib import Path

from miniroute.tools.generate_v4_1_dataset import (
    build_v4_1_records,
    split_v4_1_records,
    validate_v4_1_records,
    write_v4_1_dataset_files,
)
from miniroute.tools.validate_dataset import validate_v4_dataset_files
from miniroute.v4_schema import V4RouteLabel, V4TrainingRecord


def test_v4_1_dataset_has_expected_split_sizes(tmp_path: Path) -> None:
    splits = write_v4_1_dataset_files(tmp_path)

    assert len(splits.train) == 2400
    assert len(splits.valid) == 300
    assert len(splits.test) == 300
    assert (tmp_path / "route_v4_1_train.jsonl").exists()
    assert (tmp_path / "route_v4_1_valid.jsonl").exists()
    assert (tmp_path / "route_v4_1_test.jsonl").exists()
    assert not (tmp_path / "route_v4_train.jsonl").exists()


def test_v4_1_compound_labels_are_semantic() -> None:
    records = build_v4_1_records()
    compound = [
        record for record in records if record.label.request_mode == "compound"
    ]

    assert len(compound) == 600
    assert all("compound" in record.source for record in compound)
    assert all(
        any(marker in record.input for marker in ("并", "然后", "同时", "再", "和"))
        for record in compound
    )


def test_v4_1_connector_words_do_not_force_compound() -> None:
    labels = {record.input: record.label for record in build_v4_1_records()}

    assert labels["下载并保存这个网页正文。"].request_mode == "single"
    assert labels["保存这个网页，不是执行下载命令。"].request_mode == "single"


def test_v4_1_has_no_exact_message_overlap_across_splits() -> None:
    splits = split_v4_1_records(build_v4_1_records())
    train_inputs = {record.input for record in splits.train}
    valid_inputs = {record.input for record in splits.valid}
    test_inputs = {record.input for record in splits.test}

    assert train_inputs.isdisjoint(valid_inputs)
    assert train_inputs.isdisjoint(test_inputs)
    assert valid_inputs.isdisjoint(test_inputs)


def test_v4_1_template_families_do_not_cross_splits() -> None:
    splits = split_v4_1_records(build_v4_1_records())

    def families(records: list[V4TrainingRecord]) -> set[str]:
        return {":".join(record.source.split(":")[2:]) for record in records}

    assert families(splits.train).isdisjoint(families(splits.valid))
    assert families(splits.train).isdisjoint(families(splits.test))
    assert families(splits.valid).isdisjoint(families(splits.test))


def test_v4_1_contains_full_labels_for_known_v4_error_boundaries() -> None:
    labels = {record.input: record.label for record in build_v4_1_records()}

    expected = {
        "看一下运行记录，不要查询我的长期记忆。": V4RouteLabel(
            "status", "query", "single"
        ),
        "保存这个网页，不是执行下载命令。": V4RouteLabel(
            "content", "save", "single"
        ),
        "下载并保存这个网页正文。": V4RouteLabel(
            "action", "execute", "single"
        ),
        "我之前说过哪些项目数据？": V4RouteLabel(
            "memory", "query", "single"
        ),
        "按刚才那个来。": V4RouteLabel("unknown", "unknown", "single"),
    }

    for text, label in expected.items():
        assert labels[text] == label


def test_v4_1_dataset_passes_schema_and_semantic_validation(tmp_path: Path) -> None:
    write_v4_1_dataset_files(tmp_path)
    paths = {
        "train": tmp_path / "route_v4_1_train.jsonl",
        "valid": tmp_path / "route_v4_1_valid.jsonl",
        "test": tmp_path / "route_v4_1_test.jsonl",
    }

    schema_report = validate_v4_dataset_files(paths)
    semantic_issues = validate_v4_1_records(build_v4_1_records())

    assert schema_report.ok is True
    assert schema_report.total_records == 3000
    assert schema_report.compound_count == 600
    assert schema_report.issues == []
    assert semantic_issues == []
