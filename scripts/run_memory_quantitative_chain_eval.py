from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_quantitative_uplift import (
    build_quantitative_chain_report,
    write_quantitative_chain_markdown,
    write_quantitative_uplift_json,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="my_md/memory_optimization/eval_reports")
    parser.add_argument("--case-set", choices=("all", "common", "hard"), default="all")
    parser.add_argument(
        "--case-pack",
        choices=("standard", "comprehensive"),
        default="standard",
    )
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    cases = build_quantitative_eval_cases(
        case_set=args.case_set,
        limit=args.limit,
        case_pack=args.case_pack,
    )
    if not cases:
        print("No quantitative cases available.")
        return 1

    report = build_quantitative_chain_report(cases)
    out_dir = Path(args.out_dir)
    json_path = out_dir / "memory_quantitative_chain_eval.json"
    md_path = out_dir / "memory_quantitative_chain_eval.md"
    write_quantitative_uplift_json(report, json_path)
    write_quantitative_chain_markdown(report, md_path)
    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
