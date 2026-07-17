from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory2.eval_real_candidates import evaluate_unforced_candidates
from memory2.eval_real_report import (
    build_real_eval_summary,
    write_real_eval_json,
    write_real_eval_markdown,
)
from memory2.eval_real_samples import (
    collect_real_memory_samples,
    real_sample_to_eval_case,
)
from memory2.eval_runner import run_eval_cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", default="workspace")
    parser.add_argument("--out-dir", default="my_md/memory_optimization/eval_reports")
    parser.add_argument("--limit-per-category", type=int, default=20)
    args = parser.parse_args()

    sample_set = collect_real_memory_samples(
        Path(args.workspace),
        limit_per_category=args.limit_per_category,
    )
    cases = [real_sample_to_eval_case(sample) for sample in sample_set.samples]
    report = run_eval_cases(cases)
    candidate_result = evaluate_unforced_candidates(sample_set)
    summary = build_real_eval_summary(sample_set, report, candidate_result)

    out_dir = Path(args.out_dir)
    json_path = out_dir / "memory_real_sample_eval.json"
    md_path = out_dir / "memory_real_sample_eval.md"
    write_real_eval_json(summary, json_path)
    write_real_eval_markdown(summary, md_path)
    print(json_path)
    print(md_path)
    if report.passed and int(summary["sample_count"]) > 0:
        return 0
    if (
        report.passed
        and args.limit_per_category == 0
        and int(summary["missing_table_count"]) == 0
    ):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
