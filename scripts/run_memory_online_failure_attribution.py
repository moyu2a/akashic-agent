from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory2.eval_online_failure_attribution import (
    build_online_failure_attribution_report,
    build_online_failure_attribution_report_from_checkpoint_rows,
    write_online_failure_attribution_json,
    write_online_failure_attribution_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input-json")
    group.add_argument("--checkpoint-jsonl")
    parser.add_argument(
        "--out-dir",
        default="my_md/memory_optimization/eval_reports/online_failure_attribution",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    if args.input_json:
        payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
        report = build_online_failure_attribution_report(payload)
    else:
        rows = [
            json.loads(line)
            for line in Path(args.checkpoint_jsonl).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        report = build_online_failure_attribution_report_from_checkpoint_rows(rows)
    write_online_failure_attribution_json(
        report,
        out_dir / "online_failure_attribution.json",
    )
    write_online_failure_attribution_markdown(
        report,
        out_dir / "online_failure_attribution.md",
    )
    print(out_dir / "online_failure_attribution.json")
    print(out_dir / "online_failure_attribution.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
