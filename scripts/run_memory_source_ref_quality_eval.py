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
    write_source_ref_quality_json,
    write_source_ref_quality_markdown,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run shadow source_ref quality before/after evaluation."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--fixture-db", type=Path)
    args = parser.parse_args(argv)

    fixture_db = args.fixture_db or args.output_dir / "fixture_sessions.db"
    candidates = build_source_ref_quality_fixture(fixture_db)
    handle = open_marked_source_ref_quality_fixture_resolver(fixture_db)
    try:
        report = run_source_ref_quality_eval(
            candidates=candidates,
            source_ref_resolver=handle.resolver,
        )
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
