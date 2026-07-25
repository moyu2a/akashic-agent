from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory2.eval_source_ref_quality import (
    build_source_ref_quality_fixture,
    open_marked_source_ref_quality_fixture_resolver,
    run_source_ref_quality_eval,
    with_source_ref_quality_metadata,
    write_source_ref_quality_json,
    write_source_ref_quality_markdown,
)
from memory2.eval_source_ref_quality_cases import build_source_ref_quality_case_pack


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run shadow source_ref quality before/after evaluation."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--fixture-db", type=Path)
    parser.add_argument("--case-pack", choices=("smoke", "expanded"), default="smoke")
    parser.add_argument("--common-per-scenario", type=int, default=20)
    parser.add_argument("--hard-per-scenario", type=int, default=20)
    args = parser.parse_args(argv)

    fixture_db = args.fixture_db or args.output_dir / "fixture_sessions.db"
    if args.case_pack == "expanded":
        pack = build_source_ref_quality_case_pack(
            fixture_db,
            common_per_scenario=args.common_per_scenario,
            hard_per_scenario=args.hard_per_scenario,
        )
        candidates = pack.candidates
        report_metadata = pack.metadata
    else:
        candidates = build_source_ref_quality_fixture(fixture_db)
        report_metadata = {"case_pack": "smoke"}
    handle = open_marked_source_ref_quality_fixture_resolver(fixture_db)
    try:
        report = run_source_ref_quality_eval(
            candidates=candidates,
            source_ref_resolver=handle.resolver,
        )
        report = with_source_ref_quality_metadata(report, report_metadata)
    finally:
        handle.close()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_source_ref_quality_json(
        report,
        args.output_dir / "memory_source_ref_quality_eval.json",
    )
    write_source_ref_quality_markdown(
        report,
        args.output_dir / "memory_source_ref_quality_eval.md",
    )
    print(
        "source ref quality eval complete: "
        f"candidates={report.metrics['candidate_count']} "
        f"fetch_success={report.metrics['baseline_fetch_success_rate']}->"
        f"{report.metrics['normalized_fetch_success_rate']} "
        f"source_backed_eligible={report.metrics['baseline_source_backed_eligible_rate']}->"
        f"{report.metrics['normalized_source_backed_eligible_rate']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
