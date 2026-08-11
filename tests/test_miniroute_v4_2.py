from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from miniroute.tools.generate_v4_2_dataset import (
    REQUIRED_HARD_NEGATIVE_FAMILIES,
    build_v4_2_records,
    max_cross_split_similarity,
    normalize_for_leakage,
    split_v4_2_records,
    validate_v4_2_records,
    write_v4_2_dataset_files,
)
from miniroute.tools.validate_dataset import validate_v4_dataset_files
from miniroute.v4_schema import V4RouteLabel, V4TrainingRecord


def _source_parts(record: V4TrainingRecord) -> tuple[str, str, str, str, str]:
    parts = record.source.split(":")
    assert len(parts) == 5
    version, split, scene, mode, family = parts
    assert version == "v4_2"
    return version, split, scene, mode, family


def test_v4_2_dataset_has_expected_split_sizes_and_file_names(tmp_path: Path) -> None:
    splits = write_v4_2_dataset_files(tmp_path)

    assert len(splits.train) == 2400
    assert len(splits.valid) == 300
    assert len(splits.test) == 300
    assert {path.name for path in tmp_path.iterdir()} == {
        "route_v4_2_train.jsonl",
        "route_v4_2_valid.jsonl",
        "route_v4_2_test.jsonl",
    }


def test_v4_2_families_are_shared_without_text_leakage() -> None:
    splits = split_v4_2_records(build_v4_2_records())

    def families(records: list[V4TrainingRecord]) -> set[str]:
        return {_source_parts(record)[4] for record in records}

    train_families = families(splits.train)
    valid_families = families(splits.valid)
    test_families = families(splits.test)
    assert train_families == valid_families == test_families

    train_inputs = {record.input for record in splits.train}
    valid_inputs = {record.input for record in splits.valid}
    test_inputs = {record.input for record in splits.test}
    assert train_inputs.isdisjoint(valid_inputs)
    assert train_inputs.isdisjoint(test_inputs)
    assert valid_inputs.isdisjoint(test_inputs)

    normalized_by_split = {
        "train": {normalize_for_leakage(record.input) for record in splits.train},
        "valid": {normalize_for_leakage(record.input) for record in splits.valid},
        "test": {normalize_for_leakage(record.input) for record in splits.test},
    }
    assert normalized_by_split["train"].isdisjoint(normalized_by_split["valid"])
    assert normalized_by_split["train"].isdisjoint(normalized_by_split["test"])
    assert normalized_by_split["valid"].isdisjoint(normalized_by_split["test"])
    assert max_cross_split_similarity(splits) < 0.92


def test_v4_2_split_internal_normalized_inputs_are_unique() -> None:
    splits = split_v4_2_records(build_v4_2_records())
    for records in (splits.train, splits.valid, splits.test):
        normalized = [normalize_for_leakage(record.input) for record in records]
        counts = Counter(normalized)
        assert [text for text, count in counts.items() if count > 1] == []


def test_v4_2_compound_labels_are_semantic() -> None:
    records = build_v4_2_records()
    compound = [
        record for record in records if record.label.request_mode == "compound"
    ]

    assert len(compound) == 600
    assert all("compound" in record.source for record in compound)
    assert all(
        any(marker in record.input for marker in ("并", "同时", "和", "分别", "以及"))
        for record in compound
    )


def test_v4_2_connector_words_do_not_force_compound() -> None:
    labels = {record.input: record.label for record in build_v4_2_records()}

    assert labels["下载并保存这个网页正文。"] == V4RouteLabel(
        "action", "execute", "single"
    )
    assert labels["保存这个网页，不是执行下载命令。"] == V4RouteLabel(
        "content", "save", "single"
    )
    assert labels["运行测试并把结果写入文件。"] == V4RouteLabel(
        "action", "execute", "single"
    )


def test_v4_2_covers_required_boundary_families_and_density() -> None:
    records = build_v4_2_records()
    families_by_split: dict[str, Counter[str]] = defaultdict(Counter)
    families_by_scene_mode: dict[tuple[str, str], set[str]] = defaultdict(set)
    for record in records:
        _, split, scene, mode, family = _source_parts(record)
        families_by_split[split][family] += 1
        families_by_scene_mode[(scene, mode)].add(family)

    required = {
        "file_no_shell",
        "file_config_log",
        "status_trace_tools",
        "status_not_memory",
        "memory_past_preference",
        "memory_not_status",
        "content_save_no_download",
        "action_execute_shell",
        "unknown_capability",
        "unknown_not_action",
        "task_next_plan",
        "chat_not_profile",
    }
    all_families = set(families_by_split["train"])
    assert required <= all_families

    for family in REQUIRED_HARD_NEGATIVE_FAMILIES:
        assert families_by_split["train"][family] >= 20

    for scene in {
        "chat",
        "memory",
        "profile",
        "task",
        "file",
        "status",
        "content",
        "action",
        "unknown",
    }:
        assert len(families_by_scene_mode[(scene, "single")]) >= 3
        assert len(families_by_scene_mode[(scene, "compound")]) >= 1

    for scene in {"file", "status", "unknown", "content", "action"}:
        assert len(families_by_scene_mode[(scene, "single")]) >= 4


def test_v4_2_dataset_passes_schema_and_semantic_validation(tmp_path: Path) -> None:
    write_v4_2_dataset_files(tmp_path)
    paths = {
        "train": tmp_path / "route_v4_2_train.jsonl",
        "valid": tmp_path / "route_v4_2_valid.jsonl",
        "test": tmp_path / "route_v4_2_test.jsonl",
    }

    schema_report = validate_v4_dataset_files(paths)
    semantic_issues = validate_v4_2_records(build_v4_2_records())

    assert schema_report.ok is True
    assert schema_report.total_records == 3000
    assert schema_report.compound_count == 600
    assert schema_report.issues == []
    assert semantic_issues == []
