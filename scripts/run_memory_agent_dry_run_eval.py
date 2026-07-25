from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory2.eval_agent_dry_run import (
    run_agent_dry_run_cases,
    write_agent_dry_run_json,
    write_agent_dry_run_markdown,
)
from memory2.eval_cases import load_eval_cases


async def _amain() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", default="tests/fixtures/memory_eval_cases")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--out-dir", default="my_md/memory_optimization/eval_reports")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    cases = load_eval_cases(Path(args.case_root))
    if args.limit > 0:
        cases = cases[: args.limit]
    report = await run_agent_dry_run_cases(cases, Path(args.workspace))

    out_dir = Path(args.out_dir)
    json_path = out_dir / "memory_agent_dry_run_eval.json"
    md_path = out_dir / "memory_agent_dry_run_eval.md"
    write_agent_dry_run_json(report, json_path)
    write_agent_dry_run_markdown(report, md_path)
    print(json_path)
    print(md_path)
    return 0 if int(report.metrics["passed_case_count"]) > 0 else 1


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
