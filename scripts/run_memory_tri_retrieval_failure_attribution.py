from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory2.eval_tri_retrieval_failure_attribution import (
    build_tri_retrieval_failure_attribution_report,
    write_tri_retrieval_failure_attribution_json,
    write_tri_retrieval_failure_attribution_markdown,
)


DEFAULT_INPUT = (
    "my_md/memory_optimization/eval_reports/"
    "route_governance_small_online_v1/memory_comprehensive_online_eval.json"
)
DEFAULT_OUT_DIR = (
    "my_md/memory_optimization/eval_reports/"
    "tri_retrieval_failure_attribution_v1"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-json", default=DEFAULT_INPUT)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    report = build_tri_retrieval_failure_attribution_report(payload)
    out_dir = Path(args.out_dir)
    json_path = out_dir / "tri_retrieval_failure_attribution.json"
    markdown_path = out_dir / "tri_retrieval_failure_attribution.md"
    write_tri_retrieval_failure_attribution_json(report, json_path)
    write_tri_retrieval_failure_attribution_markdown(report, markdown_path)
    print(json_path)
    print(markdown_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
