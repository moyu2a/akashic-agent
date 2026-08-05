from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.optimization.stage1_fake_run import (
    DEFAULT_STAGE1_PROFILES,
    run_stage1_fake_profile_ab,
    write_stage1_report_json,
    write_stage1_report_markdown,
)


def _parse_profiles(raw: str) -> tuple[str, ...]:
    values = tuple(part.strip() for part in raw.split(",") if part.strip())
    return values or DEFAULT_STAGE1_PROFILES


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="my_md/optimization_profiles/stage1_fake")
    parser.add_argument(
        "--profiles",
        default=",".join(DEFAULT_STAGE1_PROFILES),
        help="Comma-separated optimization profiles.",
    )
    args = parser.parse_args()

    try:
        report = run_stage1_fake_profile_ab(profiles=_parse_profiles(args.profiles))
    except ValueError as exc:
        parser.error(str(exc))

    out_dir = Path(args.out_dir)
    json_path = out_dir / "optimization_stage1_fake_ab.json"
    md_path = out_dir / "optimization_stage1_fake_ab.md"
    write_stage1_report_json(report, json_path)
    write_stage1_report_markdown(report, md_path)
    print(json_path)
    print(md_path)
    return 0 if report.metrics["all_profiles_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
