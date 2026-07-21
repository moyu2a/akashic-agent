from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory2.eval_write_governance_cases import build_write_governance_candidates
from memory2.eval_write_governance_counts import (
    build_write_governance_count_report,
    write_write_governance_count_json,
    write_write_governance_count_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="my_md/memory_optimization/eval_reports")
    parser.add_argument("--case-set", choices=("all", "common", "hard"), default="all")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    candidates = build_write_governance_candidates(
        case_set=args.case_set,
        limit=args.limit,
    )
    if not candidates:
        print("No write governance candidates available.")
        return 1

    report = build_write_governance_count_report(candidates)
    out_dir = Path(args.out_dir)
    json_path = out_dir / "memory_write_governance_counts_eval.json"
    md_path = out_dir / "memory_write_governance_counts_eval.md"
    write_write_governance_count_json(report, json_path)
    write_write_governance_count_markdown(report, md_path)
    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
