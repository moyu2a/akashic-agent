from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory2.eval_tri_candidate_governance import (
    DEFAULT_TRI_FAILURE_ATTRIBUTION_JSON,
    build_tri_candidate_governance_report,
    write_tri_candidate_governance_report,
)


DEFAULT_OUT_DIR = (
    "my_md/memory_optimization/eval_reports/tri_candidate_governance_v1"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-pack", default="comprehensive")
    parser.add_argument("--tri-failure-json", default=DEFAULT_TRI_FAILURE_ATTRIBUTION_JSON)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    report = build_tri_candidate_governance_report(
        case_pack=args.case_pack,
        tri_failure_json=args.tri_failure_json,
    )
    json_path, markdown_path = write_tri_candidate_governance_report(
        report,
        Path(args.out_dir),
    )
    print(json_path)
    print(markdown_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
