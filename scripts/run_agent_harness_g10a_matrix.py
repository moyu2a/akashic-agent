from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.agent_harness.matrix import (
    DEFAULT_G10A_PROFILES,
    load_task_dataset,
    run_g10a_matrix,
)


def _profiles(raw: str) -> tuple[str, ...]:
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    if len(values) != 3:
        raise argparse.ArgumentTypeError("expected exactly 3 comma-separated profiles")
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the G10-A 60-turn matrix")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("my_md/test_docs/eval_suite/g10a-60turn-matrix.json"),
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--profiles", type=_profiles, default=DEFAULT_G10A_PROFILES)
    parser.add_argument("--max-react-iterations", type=int, default=12)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--git-sha", default="working-tree")
    parser.add_argument("--dataset-version", default="g10a-60turn-v1")
    parser.add_argument("--model", default="fake-model")
    parser.add_argument("--provider", default="fake")
    parser.add_argument(
        "--environment-kind",
        default="fake",
        choices=("fake",),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tasks = load_task_dataset(args.dataset)
    report = asyncio.run(
        run_g10a_matrix(
            tasks,
            output_dir=args.out_dir,
            profiles=args.profiles,
            git_sha=args.git_sha,
            dataset_version=args.dataset_version,
            model=args.model,
            provider=args.provider,
            environment_kind=args.environment_kind,
            max_react_iterations=args.max_react_iterations,
            seed=args.seed,
        )
    )
    print(args.out_dir / "g10a-matrix-report.json")
    print(f"episode_count={report.summary['episode_count']}")
    print(f"security_hard_gate_passed={report.summary['security_hard_gate_passed']}")
    print(f"formal_g10a_ready={report.summary['formal_g10a_ready']}")
    return 0 if report.summary["security_hard_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
