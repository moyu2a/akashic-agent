from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory2.eval_system_path_failure_attribution import (
    build_system_path_failure_attribution,
    build_system_path_variant_failure_attribution,
    write_system_path_failure_attribution_json,
    write_system_path_failure_attribution_markdown,
    write_system_path_variant_failure_attribution_json,
    write_system_path_variant_failure_attribution_markdown,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--baseline-mode", default="current")
    parser.add_argument("--candidate-mode", default="safe_version_replace")
    parser.add_argument("--variant-attribution", action="store_true")
    parser.add_argument("--anchor-mode", default="safe_version_replace_guided")
    parser.add_argument(
        "--comparison-modes",
        default=(
            "safe_version_replace,safe_version_replace_structured_guided,"
            "safe_version_replace_near_query_block"
        ),
    )
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    if args.variant_attribution:
        comparison_modes = [
            mode.strip()
            for mode in str(args.comparison_modes).split(",")
            if mode.strip()
        ]
        report = build_system_path_variant_failure_attribution(
            payload,
            anchor_mode=str(args.anchor_mode),
            comparison_modes=comparison_modes,
        )
        json_path = out_dir / "system_path_variant_failure_attribution.json"
        markdown_path = out_dir / "system_path_variant_failure_attribution.md"
        write_system_path_variant_failure_attribution_json(report, json_path)
        write_system_path_variant_failure_attribution_markdown(report, markdown_path)
        print(json_path)
        print(markdown_path)
        return 0

    report = build_system_path_failure_attribution(
        payload,
        baseline_mode=str(args.baseline_mode),
        candidate_mode=str(args.candidate_mode),
    )
    write_system_path_failure_attribution_json(
        report,
        out_dir / "system_path_failure_attribution.json",
    )
    write_system_path_failure_attribution_markdown(
        report,
        out_dir / "system_path_failure_attribution.md",
    )
    print(out_dir / "system_path_failure_attribution.json")
    print(out_dir / "system_path_failure_attribution.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
