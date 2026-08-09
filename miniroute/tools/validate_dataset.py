from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping

from miniroute.v1_schema import parse_training_record
from miniroute.v4_schema import SCENES, parse_v4_training_record


@dataclass(frozen=True, slots=True)
class DatasetValidationReport:
    ok: bool
    total_records: int
    high_risk_test_count: int
    issues: list[str]


@dataclass(frozen=True, slots=True)
class V4DatasetValidationReport:
    ok: bool
    total_records: int
    scene_counts: dict[str, int]
    compound_count: int
    issues: list[str]


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid jsonl: {exc.msg}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:{line_no}: row must be an object")
        rows.append(payload)
    return rows


def validate_dataset_files(paths: Mapping[str, Path]) -> DatasetValidationReport:
    strict_consistency = any("route_v2_" in path.name for path in paths.values())
    issues: list[str] = []
    total_records = 0
    high_risk_test_count = 0

    for split_name, path in paths.items():
        if not path.exists():
            issues.append(f"missing file: {split_name}")
            continue
        rows = _read_jsonl(path)
        total_records += len(rows)
        for index, row in enumerate(rows, start=1):
            parsed = parse_training_record(row, source=f"{split_name}:{index}")
            if not parsed.ok:
                issues.extend(parsed.errors)
                continue
            if parsed.record is not None:
                label = parsed.record.label
                if (
                    strict_consistency
                    and label.need_tools is False
                    and label.tool_scope != ["none"]
                ):
                    issues.append(
                        f"{split_name}:{index}: need_tools=false must use tool_scope none"
                    )
                if (
                    strict_consistency
                    and label.tool_scope == ["unknown_tools"]
                    and label.need_tools is False
                ):
                    issues.append(
                        f"{split_name}:{index}: unknown_tools requires need_tools=true"
                    )
                if split_name == "test" and label.risk_level == "high_risk":
                    high_risk_test_count += 1

    ok = not issues and high_risk_test_count >= 30
    if high_risk_test_count < 30:
        issues.append(f"high risk test count too low: {high_risk_test_count}")
    return DatasetValidationReport(
        ok=ok,
        total_records=total_records,
        high_risk_test_count=high_risk_test_count,
        issues=issues,
    )


def validate_v4_dataset_files(paths: Mapping[str, Path]) -> V4DatasetValidationReport:
    issues: list[str] = []
    total_records = 0
    scene_counts = {scene: 0 for scene in SCENES}
    compound_count = 0

    for split_name, path in paths.items():
        if not path.exists():
            issues.append(f"missing file: {split_name}")
            continue
        rows = _read_jsonl(path)
        total_records += len(rows)
        for index, row in enumerate(rows, start=1):
            parsed = parse_v4_training_record(row, source=f"{split_name}:{index}")
            if not parsed.ok:
                issues.extend(f"{split_name}:{index}: {issue}" for issue in parsed.errors)
                continue
            if parsed.record is None:
                continue
            scene_counts[parsed.record.label.scene] += 1
            if parsed.record.label.request_mode == "compound":
                compound_count += 1

    missing_scenes = [scene for scene, count in scene_counts.items() if count == 0]
    if missing_scenes:
        issues.append(f"missing scenes: {', '.join(missing_scenes)}")
    unknown_count = scene_counts.get("unknown", 0)
    if unknown_count > max(1, int(total_records * 0.08)):
        issues.append(f"unknown scene count too high: {unknown_count}")
    if compound_count < int(total_records * 0.20):
        issues.append(f"compound count too low: {compound_count}")

    return V4DatasetValidationReport(
        ok=not issues,
        total_records=total_records,
        scene_counts=scene_counts,
        compound_count=compound_count,
        issues=issues,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate MiniRoute JSONL data.")
    base_dir = Path(__file__).resolve().parents[1] / "data"
    parser.add_argument("--schema", choices=("v1", "v4"), default="v1")
    parser.add_argument("--train", type=Path)
    parser.add_argument("--valid", type=Path)
    parser.add_argument("--test", type=Path)
    args = parser.parse_args(argv)

    if args.schema == "v4":
        paths = {
            "train": args.train or base_dir / "route_v4_train.jsonl",
            "valid": args.valid or base_dir / "route_v4_valid.jsonl",
            "test": args.test or base_dir / "route_v4_test.jsonl",
        }
        report = validate_v4_dataset_files(paths)
        print(
            json.dumps(
                {
                    "schema": "v4",
                    "ok": report.ok,
                    "total_records": report.total_records,
                    "scene_counts": report.scene_counts,
                    "compound_count": report.compound_count,
                    "issues": report.issues,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if report.ok else 1

    report = validate_dataset_files(
        {
            "train": args.train or base_dir / "route_train.jsonl",
            "valid": args.valid or base_dir / "route_valid.jsonl",
            "test": args.test or base_dir / "route_test.jsonl",
        }
    )
    print(
        json.dumps(
            {
                "schema": args.schema,
                "ok": report.ok,
                "total_records": report.total_records,
                "high_risk_test_count": report.high_risk_test_count,
                "issues": report.issues,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
