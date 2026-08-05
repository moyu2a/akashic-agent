from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping

from miniroute.v1_schema import parse_training_record


@dataclass(frozen=True, slots=True)
class DatasetValidationReport:
    ok: bool
    total_records: int
    high_risk_test_count: int
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
            if split_name == "test":
                if parsed.record is not None and parsed.record.label.risk_level == "high_risk":
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate MiniRoute V1 JSONL data.")
    base_dir = Path(__file__).resolve().parents[1] / "data"
    parser.add_argument("--train", type=Path, default=base_dir / "route_train.jsonl")
    parser.add_argument("--valid", type=Path, default=base_dir / "route_valid.jsonl")
    parser.add_argument("--test", type=Path, default=base_dir / "route_test.jsonl")
    args = parser.parse_args(argv)
    report = validate_dataset_files(
        {"train": args.train, "valid": args.valid, "test": args.test}
    )
    print(
        json.dumps(
            {
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
