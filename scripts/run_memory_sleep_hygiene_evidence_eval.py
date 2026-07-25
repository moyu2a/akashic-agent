from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_sleep_hygiene_cases import build_sleep_hygiene_cases
from memory2.eval_sleep_hygiene_evidence import (
    run_sleep_hygiene_evidence_eval,
    strip_sleep_hygiene_evidence_for_target_metrics,
    write_sleep_hygiene_evidence_jsonl,
    write_sleep_hygiene_report_json,
    write_sleep_hygiene_report_markdown,
)
from memory2.eval_sleep_hygiene_patch import (
    build_sleep_hygiene_dry_run_patch,
    write_sleep_hygiene_dry_run_patch_json,
)
from memory2.eval_sleep_hygiene_provenance import build_source_ref_resolver
from memory2.eval_sleep_hygiene_source_fixture import (
    build_sleep_hygiene_source_fixture,
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
    parser.add_argument(
        "--case-set",
        choices=("standard", "hard", "all"),
        default="standard",
    )
    parser.add_argument("--hard-per-scenario", type=int, default=40)
    parser.add_argument("--write-target-metrics", action="store_true")
    parser.add_argument("--write-dry-run-patch", action="store_true")
    parser.add_argument(
        "--source-fetch-mode",
        choices=("proxy", "session-store"),
        default="proxy",
    )
    parser.add_argument("--session-db", type=Path)
    parser.add_argument(
        "--source-fixture-mode",
        choices=("none", "balanced"),
        default="none",
    )
    parser.add_argument("--source-fixture-db", type=Path)
    args = parser.parse_args(argv)

    effective_case_set = args.case_set
    if args.source_fixture_mode == "balanced":
        fixture_db = args.source_fixture_db or args.output_dir / "fixture_sessions.db"
        fixture = build_sleep_hygiene_source_fixture(
            fixture_db,
            duplicate_groups=args.duplicate_groups,
            stale_count=args.stale_count,
            low_value_count=args.low_value_count,
            retained_count=args.retained_count,
            hard_per_scenario=args.hard_per_scenario,
        )
        cases = fixture.cases
        args.source_fetch_mode = "session-store"
        args.session_db = fixture.session_db_path
        effective_case_set = "all"
    else:
        cases = build_sleep_hygiene_cases(
            case_set=args.case_set,
            duplicate_groups=args.duplicate_groups,
            stale_count=args.stale_count,
            low_value_count=args.low_value_count,
            retained_count=args.retained_count,
            hard_per_scenario=args.hard_per_scenario,
            missing_source_count=args.missing_source_count,
        )
    try:
        source_ref_resolver = build_source_ref_resolver(
            args.source_fetch_mode,
            session_db_path=args.session_db,
        )
    except ValueError as exc:
        parser.error(str(exc))
    report = run_sleep_hygiene_evidence_eval(
        cases=cases,
        source_ref_resolver=source_ref_resolver,
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
    if args.write_dry_run_patch:
        write_sleep_hygiene_dry_run_patch_json(
            build_sleep_hygiene_dry_run_patch(report.records),
            args.output_dir / "memory_sleep_hygiene_dry_run_patch.json",
        )

    if args.write_target_metrics:
        target_report = build_target_metric_report(
            build_quantitative_eval_cases(limit=8),
            online_hygiene_records=strip_sleep_hygiene_evidence_for_target_metrics(
                report.records
            ),
            online_checkpoint_source=(
                "sleep_hygiene_source_backed_fixture"
                if args.source_fixture_mode == "balanced"
                else "sleep_hygiene_session_store"
                if args.source_fetch_mode == "session-store"
                else "sleep_hygiene_evidence_eval_proxy"
            ),
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
        f"case_set={effective_case_set} "
        f"cases={report.metrics['case_count']} "
        f"scanned_active_items={report.metrics['scanned_active_item_count']} "
        f"evidence_rows={report.metrics['evaluated_evidence_row_count']} "
        f"duplicate_candidate_rate={report.metrics['duplicate_merge_rate']} "
        f"stale_candidate_rate={report.metrics['stale_cleanup_rate']} "
        f"low_value_candidate_rate={report.metrics['low_value_cleanup_rate']} "
        f"source_fetch_mode={args.source_fetch_mode} "
        f"source_fixture_mode={args.source_fixture_mode} "
        f"retention_rate={report.metrics['post_consolidation_recall_retention_rate']} "
        f"false_positive_cleanup_rate={report.metrics['false_positive_cleanup_rate']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
