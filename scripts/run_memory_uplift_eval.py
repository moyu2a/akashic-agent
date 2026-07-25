from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory2.eval_cases import load_eval_cases
from memory2.eval_runner import run_eval_cases
from memory2.eval_uplift import (
    build_uplift_report,
    write_uplift_json,
    write_uplift_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", default="tests/fixtures/memory_eval_cases")
    parser.add_argument("--out-dir", default="my_md/memory_optimization/eval_reports")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    cases = load_eval_cases(Path(args.case_root))
    if args.limit > 0:
        cases = cases[: args.limit]
    eval_report = run_eval_cases(cases)
    uplift_report = build_uplift_report(cases, eval_report)

    out_dir = Path(args.out_dir)
    json_path = out_dir / "memory_uplift_eval.json"
    md_path = out_dir / "memory_uplift_eval.md"
    write_uplift_json(uplift_report, json_path)
    write_uplift_markdown(uplift_report, md_path)
    print(json_path)
    print(md_path)
    return 0 if int(uplift_report.metrics["feature_record_count"]) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
