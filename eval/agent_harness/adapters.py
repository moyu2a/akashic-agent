from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any, Protocol

from .environments import EvalEnvironment
from .events import EventLedger, event_to_dict
from .protocol import EpisodeResult, RunManifest, TaskSpec


class AgentAdapter(Protocol):
    async def run_episode(
        self,
        task: TaskSpec,
        environment: EvalEnvironment,
        manifest: RunManifest,
    ) -> EpisodeResult: ...


def task_from_miniroute_record(record: dict[str, object], *, case_id: str) -> TaskSpec:
    from miniroute.v1_schema import parse_training_record

    parsed = parse_training_record(record, source=case_id)
    if not parsed.ok or parsed.record is None:
        return TaskSpec(
            case_id=case_id,
            category="router",
            router_decision=None,
            router_parse_ok=False,
            router_parse_errors=tuple(parsed.errors),
            grader_names=("router",),
        )

    label = parsed.record.label.to_dict()
    return TaskSpec(
        case_id=case_id,
        category="router",
        steps=({"role": "user", "text": parsed.record.input},),
        router_decision=label,
        router_parse_ok=True,
        expected_outcome={"state": {}},
        grader_names=("router",),
    )


class DeterministicFakeAdapter:
    """Small deterministic adapter for contract, report, and replay testing."""

    def __init__(self, *, max_react_iterations: int = 12) -> None:
        if max_react_iterations < 1:
            raise ValueError("max_react_iterations must be at least 1")
        self.max_react_iterations = max_react_iterations

    async def run_episode(
        self,
        task: TaskSpec,
        environment: EvalEnvironment,
        manifest: RunManifest,
    ) -> EpisodeResult:
        environment.reset(manifest.seed)
        ledger = EventLedger(run_id=manifest.run_id, episode_id=task.case_id)
        ledger.append(
            "episode_started",
            "fake_adapter",
            {
                "case_id": task.case_id,
                "category": task.category,
                "governance_profile": manifest.governance_profile,
            },
        )

        if task.router_decision is not None or task.router_parse_ok is not None:
            ledger.append(
                "router_decision",
                "router",
                {
                    "decision": task.router_decision,
                    "parse_ok": task.router_parse_ok,
                    "parse_errors": list(task.router_parse_errors),
                },
            )

        steps = task.steps or ({"role": "user", "text": task.case_id},)
        react_iterations = 0
        tool_count = 0
        for turn_index, step in enumerate(steps):
            if react_iterations >= self.max_react_iterations:
                break
            react_iterations += 1
            ledger.append(
                "turn_started",
                "fake_adapter",
                {"role": step.get("role", "user")},
                turn_index=turn_index,
            )
            ledger.append(
                "context_rendered",
                "fake_adapter",
                {"text_length": len(step.get("text", ""))},
                turn_index=turn_index,
            )
            ledger.append(
                "llm_call_started",
                "fake_provider",
                {"model": manifest.model},
                turn_index=turn_index,
            )
            await asyncio.sleep(0)
            ledger.append(
                "llm_call_finished",
                "fake_provider",
                {"prompt_tokens": 100, "completion_tokens": 20},
                turn_index=turn_index,
            )

        state = environment.inspect_state()
        for tool_index, tool in enumerate(task.expected_tools):
            action = (
                task.expected_policy_actions[tool_index]
                if tool_index < len(task.expected_policy_actions)
                else ("deny" if tool in task.forbidden_tools else "allow")
            )
            ledger.append(
                "tool_requested",
                "fake_agent",
                {"tool": tool},
                turn_index=min(tool_index, max(react_iterations - 1, 0)),
            )
            ledger.append(
                "policy_decision",
                "fake_governance",
                {"tool": tool, "policy_action": action},
                turn_index=min(tool_index, max(react_iterations - 1, 0)),
            )
            if action in {"deny", "block", "defer"}:
                ledger.append(
                    "tool_skipped",
                    "fake_governance",
                    {"tool": tool, "policy_action": action},
                )
                continue

            ledger.append("tool_executed", "fake_tool", {"tool": tool})
            tool_count += 1
            if isinstance(environment, object) and hasattr(environment, "mutate"):
                expected_state = task.expected_outcome.get("state", {})
                if isinstance(expected_state, dict):
                    environment.mutate(expected_state)
                    ledger.append(
                        "state_mutated",
                        "fake_environment",
                        {"keys": sorted(expected_state)},
                    )

        if (
            not task.expected_tools
            and isinstance(environment, object)
            and hasattr(environment, "mutate")
        ):
            expected_state = task.expected_outcome.get("state", {})
            if isinstance(expected_state, dict):
                environment.mutate(expected_state)
                if expected_state:
                    ledger.append(
                        "state_mutated",
                        "fake_environment",
                        {"keys": sorted(expected_state)},
                    )

        final_state = environment.inspect_state()
        expected_state = task.expected_outcome.get("state", task.expected_outcome)
        outcome_passed = isinstance(expected_state, dict) and all(
            final_state.get(key) == value for key, value in expected_state.items()
        )
        final_reply = str(task.expected_outcome.get("reply", "fake episode completed"))
        ledger.append("reply_emitted", "fake_adapter", {"reply": final_reply})
        ledger.append(
            "episode_finished",
            "fake_adapter",
            {"status": "PASS" if outcome_passed else "FAIL"},
        )

        total_tokens = react_iterations * 120
        result = EpisodeResult(
            episode_id=task.case_id,
            status="PASS" if outcome_passed else "FAIL",
            outcome_passed=outcome_passed,
            final_reply=final_reply,
            events=tuple(event_to_dict(event) for event in ledger.events),
            metrics={
                "prompt_tokens": react_iterations * 100,
                "completion_tokens": react_iterations * 20,
                "total_tokens": total_tokens,
                "latency_ms": react_iterations * 10,
                "tool_count": tool_count,
                "react_iterations": react_iterations,
                "max_react_iterations": self.max_react_iterations,
            },
        )
        return replace(result, metrics={**result.metrics, "final_state": final_state})
