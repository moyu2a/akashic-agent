from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

TaskExecutionAction = Literal[
    "inactive", "replay", "continue", "retry", "inspect", "abort"
]
TaskExecutionPhase = Literal[
    "inactive",
    "claim",
    "work",
    "waiting_authorization",
    "finish",
    "terminal",
]

_KNOWN_CAPABILITIES = frozenset(
    {
        "task_execution.begin",
        "task_execution.inspect",
        "task_execution.finish",
        "task_execution.defer",
        "task_execution.abort",
    }
)
_WORK_CAPABILITIES = frozenset(
    {
        "task_execution.finish",
        "task_execution.defer",
    }
)
_CLAIM_CAPABILITIES = frozenset(
    {
        "task_execution.begin",
        "task_execution.inspect",
    }
)
_WAITING_CAPABILITIES = frozenset(
    {
        "task_execution.inspect",
        "task_execution.abort",
    }
)
_FINISH_CAPABILITIES = frozenset(
    {
        "task_execution.finish",
        "task_execution.defer",
        "task_execution.abort",
        "task_execution.inspect",
    }
)

_BACKGROUND_TERMS = (
    "后台任务",
    "后台 job",
    "job_id",
    "subagent",
    "spawn",
)
_TASK_PLAN_TERMS = (
    "制定计划",
    "创建计划",
    "三步计划",
    "分步骤",
    "拆成步骤",
    "当前任务",
    "当前进度",
    "做到哪一步",
    "任务进度",
    "标记",
    "完成第",
    "更新步骤",
    "更新任务",
    "跳过",
)
_RETRY_TERMS = ("重试", "retry")
_ABORT_TERMS = ("终止执行", "停止执行", "取消执行", "abort")
_ABORT_RE = re.compile(r"(?:终止|停止|取消).{0,8}?执行", re.IGNORECASE)
_INSPECT_TERMS = ("查看执行状态", "执行进度", "执行状态", "inspect execution")
_CONTINUE_TERMS = ("继续执行", "执行下一步", "下一步执行", "continue execution")
_NEGATED_EXECUTION_RE = re.compile(
    r"(?:请勿|不要|不再|无需|无须|不用|不必|暂时别|暂不|先别|先不|别|不)"
    r"\s*(?:再\s*)?(?:继续\s*执行|执行\s*下一步|重试|终止\s*执行|停止\s*执行|取消\s*执行|查看\s*执行状态|执行状态|abort|retry|inspect\s+execution)"
    r"|(?:do\s+not|don't|dont|never)\s+(?:continue\s+execution|execute\s+next\s+step|retry|abort|inspect\s+execution)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TaskExecutionTurnContract:
    active: bool
    action: TaskExecutionAction
    phase: TaskExecutionPhase
    attempt_id: str | None
    target_step_id: str | None
    required_capabilities: frozenset[str]
    allowed_capabilities: frozenset[str]
    allowed_risks: frozenset[str]
    work_call_budget: int
    tool_search_budget: int
    completion_capability: str | None
    reason: str
    matched_terms: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "required_capabilities", frozenset(self.required_capabilities)
        )
        object.__setattr__(
            self, "allowed_capabilities", frozenset(self.allowed_capabilities)
        )
        object.__setattr__(self, "allowed_risks", frozenset(self.allowed_risks))
        object.__setattr__(self, "matched_terms", tuple(self.matched_terms))

        if self.action not in {
            "inactive",
            "replay",
            "continue",
            "retry",
            "inspect",
            "abort",
        }:
            raise ValueError("unsupported TaskExecution action")
        if self.phase not in {
            "inactive",
            "claim",
            "work",
            "waiting_authorization",
            "finish",
            "terminal",
        }:
            raise ValueError("unsupported TaskExecution phase")
        if type(self.work_call_budget) is not int or self.work_call_budget < 0:
            raise ValueError("work call budget must be a non-negative integer")
        if type(self.tool_search_budget) is not int or self.tool_search_budget < 0:
            raise ValueError("tool search budget must be a non-negative integer")
        if not all(
            isinstance(item, str)
            for item in self.required_capabilities
            | self.allowed_capabilities
            | self.allowed_risks
        ):
            raise ValueError("capabilities and risks must be strings")
        if (
            self.required_capabilities | self.allowed_capabilities
        ) - _KNOWN_CAPABILITIES:
            raise ValueError("unsupported TaskExecution capability")

        if not self.active or self.action == "inactive":
            if (
                self.active
                or self.action != "inactive"
                or self.phase != "inactive"
                or self.attempt_id is not None
                or self.target_step_id is not None
                or self.required_capabilities
                or self.allowed_capabilities
                or self.allowed_risks
                or self.work_call_budget != 0
                or self.tool_search_budget != 0
                or self.completion_capability is not None
            ):
                raise ValueError("inactive TaskExecution contract must use empty state")
            return

        if self.phase == "inactive":
            raise ValueError("active TaskExecution contract requires an active phase")
        if self.action == "replay":
            if (
                self.phase != "terminal"
                or not _valid_id(self.attempt_id)
                or self.target_step_id is not None
                or self.required_capabilities
                or self.allowed_capabilities
                or self.allowed_risks
                or self.work_call_budget != 0
                or self.tool_search_budget != 0
                or self.completion_capability is not None
            ):
                raise ValueError("replay contract requires terminal runtime-only state")
            return
        if self.required_capabilities - self.allowed_capabilities:
            raise ValueError("required capabilities must be allowed")
        if self.completion_capability not in self.required_capabilities:
            raise ValueError("completion capability must be required")
        if len(self.required_capabilities) != 1:
            raise ValueError("exactly one TaskExecution capability must be required")
        if self.action == "retry" and not _valid_id(self.target_step_id):
            raise ValueError("retry contract requires a runtime-resolved target step")
        if (
            self.action != "retry"
            and self.target_step_id is not None
            and not _valid_id(self.target_step_id)
        ):
            raise ValueError("target step identity must be a non-empty string")

        if self.phase == "claim":
            if (
                not self.allowed_capabilities <= _CLAIM_CAPABILITIES
                or self.allowed_risks
                or self.work_call_budget != 0
                or self.tool_search_budget != 0
            ):
                raise ValueError("claim phase permits only begin and inspect")
        elif self.phase == "work":
            if (
                not _WORK_CAPABILITIES <= self.allowed_capabilities
                or "task_execution.abort" not in self.allowed_capabilities
                or self.allowed_risks != frozenset({"read-only"})
                or self.work_call_budget < 1
                or self.tool_search_budget != 1
            ):
                raise ValueError("work phase permits exact read-only execution")
        elif self.phase == "waiting_authorization":
            if (
                not self.allowed_capabilities <= _WAITING_CAPABILITIES
                or self.allowed_risks
                or self.work_call_budget != 0
                or self.tool_search_budget != 0
            ):
                raise ValueError("waiting phase permits only inspect and abort")
        elif self.phase == "finish":
            if (
                not self.allowed_capabilities <= _FINISH_CAPABILITIES
                or self.allowed_risks
                or self.work_call_budget != 0
                or self.tool_search_budget != 0
            ):
                raise ValueError("finish phase cannot permit work tools")
        elif self.phase == "terminal":
            if (
                self.required_capabilities
                or self.allowed_capabilities
                or self.allowed_risks
                or self.work_call_budget != 0
                or self.tool_search_budget != 0
                or self.completion_capability is not None
            ):
                raise ValueError("terminal phase cannot permit work capabilities")

    @classmethod
    def inactive(cls) -> TaskExecutionTurnContract:
        return cls(
            active=False,
            action="inactive",
            phase="inactive",
            attempt_id=None,
            target_step_id=None,
            required_capabilities=frozenset(),
            allowed_capabilities=frozenset(),
            allowed_risks=frozenset(),
            work_call_budget=0,
            tool_search_budget=0,
            completion_capability=None,
            reason="no_task_execution_intent",
            matched_terms=(),
        )

    def to_trace_metadata(self) -> dict[str, object]:
        return {
            "active": self.active,
            "action": self.action,
            "phase": self.phase,
            "attempt_id": self.attempt_id,
            "target_step_id": self.target_step_id,
            "required_capabilities": sorted(self.required_capabilities),
            "allowed_capabilities": sorted(self.allowed_capabilities),
            "allowed_risks": sorted(self.allowed_risks),
            "work_call_budget": self.work_call_budget,
            "tool_search_budget": self.tool_search_budget,
            "completion_capability": self.completion_capability,
            "reason": self.reason,
            "matched_terms": list(self.matched_terms),
        }


def infer_task_execution_contract(
    user_text: str,
    metadata: Mapping[str, Any],
) -> TaskExecutionTurnContract:
    if not bool(metadata.get("task_execution_enabled")):
        return TaskExecutionTurnContract.inactive()

    replay_attempt_id = metadata.get("request_replay_attempt_id")
    if _valid_id(replay_attempt_id):
        return TaskExecutionTurnContract(
            active=True,
            action="replay",
            phase="terminal",
            attempt_id=replay_attempt_id,
            target_step_id=None,
            required_capabilities=frozenset(),
            allowed_capabilities=frozenset(),
            allowed_risks=frozenset(),
            work_call_budget=0,
            tool_search_budget=0,
            completion_capability=None,
            reason="runtime_request_replay",
            matched_terms=(),
        )

    text = str(user_text or "")
    action, matched_terms = _parse_task_execution_intent(text)
    if _matched_terms(text, _BACKGROUND_TERMS) or _matched_terms(
        text, _TASK_PLAN_TERMS
    ):
        return TaskExecutionTurnContract.inactive()
    if not bool(metadata.get("has_active_task")):
        return TaskExecutionTurnContract.inactive()

    if action == "retry":
        target_step_id = metadata.get("latest_retryable_step_id")
        if not _valid_id(target_step_id):
            return TaskExecutionTurnContract.inactive()
        return _claim_contract(
            "retry",
            matched_terms,
            target_step_id=target_step_id,
        )

    if action == "abort":
        return TaskExecutionTurnContract(
            active=True,
            action="abort",
            phase="finish",
            attempt_id=None,
            target_step_id=None,
            required_capabilities=frozenset({"task_execution.abort"}),
            allowed_capabilities=frozenset({"task_execution.abort"}),
            allowed_risks=frozenset(),
            work_call_budget=0,
            tool_search_budget=0,
            completion_capability="task_execution.abort",
            reason="abort_execution",
            matched_terms=matched_terms,
        )

    if action == "inspect":
        return TaskExecutionTurnContract(
            active=True,
            action="inspect",
            phase="claim",
            attempt_id=None,
            target_step_id=None,
            required_capabilities=frozenset({"task_execution.inspect"}),
            allowed_capabilities=frozenset({"task_execution.inspect"}),
            allowed_risks=frozenset(),
            work_call_budget=0,
            tool_search_budget=0,
            completion_capability="task_execution.inspect",
            reason="inspect_execution",
            matched_terms=matched_terms,
        )

    if action == "continue":
        return _claim_contract("continue", matched_terms)
    return TaskExecutionTurnContract.inactive()


def detect_task_execution_intent(user_text: str) -> bool:
    action, _ = _parse_task_execution_intent(str(user_text or ""))
    return action != "inactive"


def _parse_task_execution_intent(
    text: str,
) -> tuple[Literal["inactive", "continue", "retry", "inspect", "abort"], tuple[str, ...]]:
    if _matched_terms(text, _BACKGROUND_TERMS) or _NEGATED_EXECUTION_RE.search(text):
        return "inactive", ()
    retry_terms = _matched_terms(text, _RETRY_TERMS)
    if retry_terms:
        return "retry", retry_terms
    abort_terms = _dedupe_terms(
        (*_matched_terms(text, _ABORT_TERMS), *_matched_regex_terms(text, _ABORT_RE))
    )
    if abort_terms:
        return "abort", abort_terms
    inspect_terms = _matched_terms(text, _INSPECT_TERMS)
    if inspect_terms:
        return "inspect", inspect_terms
    continue_terms = _matched_terms(text, _CONTINUE_TERMS)
    if continue_terms:
        return "continue", continue_terms
    return "inactive", ()


def _claim_contract(
    action: Literal["continue", "retry"],
    matched_terms: tuple[str, ...],
    *,
    target_step_id: str | None = None,
) -> TaskExecutionTurnContract:
    return TaskExecutionTurnContract(
        active=True,
        action=action,
        phase="claim",
        attempt_id=None,
        target_step_id=target_step_id,
        required_capabilities=frozenset({"task_execution.begin"}),
        allowed_capabilities=frozenset(
            {"task_execution.begin", "task_execution.inspect"}
        ),
        allowed_risks=frozenset(),
        work_call_budget=0,
        tool_search_budget=0,
        completion_capability="task_execution.begin",
        reason=f"{action}_execution",
        matched_terms=matched_terms,
    )


def _matched_terms(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    normalized = text.lower()
    return tuple(term for term in terms if term.lower() in normalized)


def _matched_regex_terms(text: str, pattern: re.Pattern[str]) -> tuple[str, ...]:
    return tuple(match.group(0) for match in pattern.finditer(text))


def _dedupe_terms(items: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(items))


def _valid_id(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
