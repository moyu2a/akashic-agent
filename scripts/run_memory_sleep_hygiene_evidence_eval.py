from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_sleep_hygiene_evidence import (
    run_sleep_hygiene_evidence_eval,
    write_sleep_hygiene_evidence_jsonl,
    write_sleep_hygiene_report_json,
    write_sleep_hygiene_report_markdown,
)
from memory2.eval_target_metrics import (
    build_target_metric_report,
    write_target_metric_json,
    write_target_metric_markdown,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic sleep consolidation hygiene evidence evaluation."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--duplicate-groups", type=int, default=120)
    parser.add_argument("--stale-count", type=int, default=120)
    parser.add_argument("--low-value-count", type=int, default=120)
    parser.add_argument("--retained-count", type=int, default=120)
    parser.add_argument("--missing-source-count", type=int, default=40)
    parser.add_argument("--write-target-metrics", action="store_true")
    args = parser.parse_args(argv)

    report = run_sleep_hygiene_evidence_eval(
        duplicate_groups=args.duplicate_groups,
        stale_count=args.stale_count,
        low_value_count=args.low_value_count,
        retained_count=args.retained_count,
        missing_source_count=args.missing_source_count,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_sleep_hygiene_evidence_jsonl(
        report.records,
        args.output_dir / "memory_sleep_hygiene_evidence.jsonl",
    )
    write_sleep_hygiene_report_json(
        report,
        args.output_dir / "memory_sleep_hygiene_evidence_eval.json",
    )
    write_sleep_hygiene_report_markdown(
        report,
        args.output_dir / "memory_sleep_hygiene_evidence_eval.md",
    )

    if args.write_target_metrics:
        target_report = build_target_metric_report(
            build_quantitative_eval_cases(limit=8),
            online_hygiene_records=report.records,
            online_checkpoint_source="sleep_hygiene_evidence_eval_proxy",
        )
        write_target_metric_json(
            target_report,
            args.output_dir / "memory_target_metric_sleep_hygiene.json",
        )
        write_target_metric_markdown(
            target_report,
            args.output_dir / "memory_target_metric_sleep_hygiene.md",
        )

    print(
        "sleep hygiene evidence eval complete: "
        f"cases={report.metrics['case_count']} "
        f"scanned_active_items={report.metrics['scanned_active_item_count']} "
        f"evidence_rows={report.metrics['evaluated_evidence_row_count']} "
        f"duplicate_candidate_rate={report.metrics['duplicate_merge_rate']} "
        f"stale_candidate_rate={report.metrics['stale_cleanup_rate']} "
        f"low_value_candidate_rate={report.metrics['low_value_cleanup_rate']} "
        f"retention_rate={report.metrics['post_consolidation_recall_retention_rate']} "
        f"false_positive_cleanup_rate={report.metrics['false_positive_cleanup_rate']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
