from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable

from .events import sanitize_payload
from .protocol import EpisodeResult, RunManifest, TaskSpec
from .replay import save_replay


@dataclass(frozen=True)
class ReportPaths:
    json_path: Path
    markdown_path: Path
    replay_dir: Path


def _result_payload(result: EpisodeResult) -> dict[str, Any]:
    payload = result.to_dict()
    sanitized = sanitize_payload(payload)
    if not isinstance(sanitized, dict):
        raise TypeError("episode result must sanitize to an object")
    return sanitized


def write_run_report(
    output_dir: Path,
    *,
    manifest: RunManifest,
    tasks: Iterable[TaskSpec],
    results: Iterable[EpisodeResult],
    summary: dict[str, object] | None = None,
) -> ReportPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    replay_dir = output_dir / "replays"
    replay_dir.mkdir(parents=True, exist_ok=True)
    task_list = list(tasks)
    result_list = list(results)
    result_payloads = [_result_payload(result) for result in result_list]
    report = {
        "manifest": manifest.to_dict(),
        "tasks": [task.to_dict() for task in task_list],
        "results": result_payloads,
        "summary": summary or {},
    }
    json_path = output_dir / "run-report.json"
    markdown_path = output_dir / "run-report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for result in result_list:
        events = []
        for event in result.events:
            if isinstance(event, dict):
                events.append(event)
        save_replay(replay_dir / f"{result.episode_id}.json", events_to_records(events))
    lines = [
        "# Agent Harness Run Report",
        "",
        f"- Run: `{manifest.run_id}`",
        f"- Dataset: `{manifest.dataset_version}`",
        f"- Profile: `{manifest.governance_profile}`",
        f"- Environment: `{manifest.environment_kind}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in sorted((summary or {}).items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Episodes", ""])
    for result in result_list:
        lines.append(
            f"- `{result.episode_id}`: `{result.status}`, "
            f"tokens=`{result.metrics.get('total_tokens', 0)}`, "
            f"latency_ms=`{result.metrics.get('latency_ms', 0)}`"
        )
        if result.events:
            lines.append("  - trace: `[REDACTED]` payloads are sanitized")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ReportPaths(json_path, markdown_path, replay_dir)


def events_to_records(events: list[dict[str, Any]]) -> list[Any]:
    from .events import EventRecord

    records: list[EventRecord] = []
    for event in events:
        records.append(
            EventRecord(
                run_id=str(event.get("run_id", "")),
                episode_id=str(event.get("episode_id", "")),
                event_index=int(event.get("event_index", len(records))),
                turn_index=int(event.get("turn_index", 0)),
                timestamp=str(event.get("timestamp", "")),
                event_type=str(event.get("event_type", "")),
                component=str(event.get("component", "")),
                payload=dict(event.get("payload", {})),
                payload_hash=str(event.get("payload_hash", "")),
            )
        )
    return records
