from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval.agent_harness.adapters import DeterministicFakeAdapter
from eval.agent_harness.environments import DeterministicFakeEnvironment
from eval.agent_harness.reports import write_run_report
from eval.agent_harness.replay import load_replay, verify_replay
from eval.agent_harness.runner import HarnessRunner
from eval.agent_harness.protocol import TaskSpec


def _load_dataset(path: Path) -> list[TaskSpec]:
    raw = path.read_text(encoding="utf-8")
    try:
        payload: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "dataset must be JSON-compatible YAML; install PyYAML for general YAML"
        ) from exc
    if isinstance(payload, dict):
        payload = payload.get("tasks", [])
    if not isinstance(payload, list):
        raise ValueError("dataset must contain a list or a tasks list")
    return [TaskSpec.from_dict(item) for item in payload if isinstance(item, dict)]


def _run(args: argparse.Namespace) -> int:
    tasks = _load_dataset(Path(args.dataset))
    if args.repeat is not None:
        tasks = [
            TaskSpec.from_dict({**task.to_dict(), "repeat_count": args.repeat})
            for task in tasks
        ]
    if args.environment != "fake":
        raise ValueError("only --environment fake is implemented in this phase")
    runner = HarnessRunner(
        adapter=DeterministicFakeAdapter(
            max_react_iterations=args.max_react_iterations
        ),
        environment_factory=DeterministicFakeEnvironment,
        git_sha=args.git_sha,
        dataset_version=args.dataset_version,
        model=args.model,
        provider="fake",
        governance_profile=args.profile,
    )
    report = asyncio.run(runner.run(tasks, seed=args.seed))
    paths = write_run_report(
        Path(args.out_dir),
        manifest=report.manifest,
        tasks=report.tasks,
        results=report.results,
        summary=report.summary,
    )
    print(paths.json_path)
    print(paths.markdown_path)
    return 0


def _replay(args: argparse.Namespace) -> int:
    path = Path(args.run_dir) / "replays" / f"{args.episode}.json"
    events = load_replay(path)
    valid = verify_replay(events)
    print(json.dumps({"episode": args.episode, "valid": valid}, ensure_ascii=False))
    return 0 if valid else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent Evaluation Harness v2")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run")
    run.add_argument("--dataset", required=True)
    run.add_argument("--environment", default="fake", choices=("fake",))
    run.add_argument("--profile", default="full_governance")
    run.add_argument("--repeat", type=int)
    run.add_argument("--max-react-iterations", type=int, default=12)
    run.add_argument("--out-dir", required=True)
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--git-sha", default="working-tree")
    run.add_argument("--dataset-version", default="agent-harness-v2")
    run.add_argument("--model", default="fake-model")
    run.set_defaults(handler=_run)

    replay = subparsers.add_parser("replay")
    replay.add_argument("--run-dir", required=True)
    replay.add_argument("--episode", required=True)
    replay.set_defaults(handler=_replay)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
