from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
from statistics import median
from typing import Callable, Sequence
import uuid

from .adapters import AgentAdapter
from .environments import EvalEnvironment
from .protocol import EpisodeResult, RunManifest, TaskSpec


@dataclass(frozen=True)
class HarnessRun:
    manifest: RunManifest
    tasks: tuple[TaskSpec, ...]
    results: tuple[EpisodeResult, ...]
    summary: dict[str, object]


def _dataset_hash(tasks: Sequence[TaskSpec]) -> str:
    payload = [task.to_dict() for task in tasks]
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(
        len(ordered) - 1,
        max(0, int(round((percentile / 100) * (len(ordered) - 1)))),
    )
    return ordered[index]


class HarnessRunner:
    def __init__(
        self,
        *,
        adapter: AgentAdapter,
        environment_factory: Callable[[], EvalEnvironment],
        git_sha: str,
        dataset_version: str,
        model: str,
        provider: str,
        governance_profile: str,
        runner_version: str = "agent-harness-v2",
        environment_kind: str = "fake",
    ) -> None:
        self.adapter = adapter
        self.environment_factory = environment_factory
        self.git_sha = git_sha
        self.dataset_version = dataset_version
        self.model = model
        self.provider = provider
        self.governance_profile = governance_profile
        self.runner_version = runner_version
        self.environment_kind = environment_kind

    async def run(self, tasks: Sequence[TaskSpec], *, seed: int = 0) -> HarnessRun:
        if not tasks:
            raise ValueError("at least one task is required")
        run_id = f"harness-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
        results: list[EpisodeResult] = []
        for task in tasks:
            for repeat_index in range(task.repeat_count):
                manifest = RunManifest(
                    run_id=run_id,
                    git_sha=self.git_sha,
                    dataset_version=self.dataset_version,
                    dataset_hash=_dataset_hash(tasks),
                    model=self.model,
                    provider=self.provider,
                    config_hash=hashlib.sha256(
                        self.governance_profile.encode("utf-8")
                    ).hexdigest(),
                    governance_profile=self.governance_profile,
                    environment_kind=self.environment_kind,
                    seed=seed + repeat_index,
                    repeat_index=repeat_index,
                    runner_version=self.runner_version,
                )
                environment = self.environment_factory()
                try:
                    result = await self.adapter.run_episode(task, environment, manifest)
                finally:
                    environment.cleanup()
                results.append(
                    replace(
                        result,
                        episode_id=f"{task.case_id}-r{repeat_index}",
                        metrics={
                            **result.metrics,
                            "case_id": task.case_id,
                            "category": task.category,
                            "repeat_index": repeat_index,
                        },
                    )
                )

        latency = [
            float(result.metrics["latency_ms"])
            for result in results
            if result.metrics.get("latency_ms") is not None
        ]
        summary = {
            "episode_count": len(results),
            "passed_count": sum(result.status == "PASS" for result in results),
            "failed_count": sum(result.status != "PASS" for result in results),
            "mean_total_tokens": (
                sum(float(result.metrics.get("total_tokens", 0)) for result in results)
                / len(results)
            ),
            "median_latency_ms": median(latency) if latency else 0.0,
            "p50_latency_ms": _percentile(latency, 50),
            "p95_latency_ms": _percentile(latency, 95),
            "total_tool_count": sum(
                int(result.metrics.get("tool_count", 0)) for result in results
            ),
        }
        manifest = RunManifest(
            run_id=run_id,
            git_sha=self.git_sha,
            dataset_version=self.dataset_version,
            dataset_hash=_dataset_hash(tasks),
            model=self.model,
            provider=self.provider,
            config_hash=hashlib.sha256(
                self.governance_profile.encode("utf-8")
            ).hexdigest(),
            governance_profile=self.governance_profile,
            environment_kind=self.environment_kind,
            seed=seed,
            repeat_index=0,
            runner_version=self.runner_version,
        )
        return HarnessRun(
            manifest=manifest,
            tasks=tuple(tasks),
            results=tuple(results),
            summary=summary,
        )
