from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Mapping

INTENTS: tuple[str, ...] = (
    "chat",
    "memory_query",
    "profile_update",
    "task_plan",
    "content_save",
    "file_read",
    "tool_execution",
    "status_query",
)

RISK_LEVELS: tuple[str, ...] = ("none", "read_only", "write", "high_risk")

TOOL_SCOPES: tuple[str, ...] = (
    "none",
    "memory_tools",
    "content_tools",
    "file_read_tools",
    "file_write_tools",
    "shell_tools",
    "task_tools",
    "observe_tools",
)

DEFAULT_INSTRUCTION = "判断用户请求的意图、记忆需求、工具需求、工具范围和风险等级，并只输出 JSON。"


@dataclass(frozen=True, slots=True)
class RouteLabel:
    intent: str
    need_memory: bool
    need_tools: bool
    tool_scope: list[str] = field(default_factory=list)
    risk_level: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "need_memory": self.need_memory,
            "need_tools": self.need_tools,
            "tool_scope": list(self.tool_scope),
            "risk_level": self.risk_level,
        }


@dataclass(frozen=True, slots=True)
class TrainingRecord:
    instruction: str
    input: str
    label: RouteLabel
    source: str

    def to_training_json(self) -> dict[str, object]:
        return {
            "conversations": [
                {
                    "role": "user",
                    "content": f"{self.instruction}\n\n用户请求：{self.input}",
                },
                {
                    "role": "assistant",
                    "content": json.dumps(self.label.to_dict(), ensure_ascii=False),
                },
            ]
        }


@dataclass(frozen=True, slots=True)
class ParsedTrainingRecord:
    ok: bool
    errors: list[str]
    record: TrainingRecord | None = None


def parse_training_record(
    record: Mapping[str, Any], *, source: str = "unknown"
) -> ParsedTrainingRecord:
    errors: list[str] = []

    conversations = record.get("conversations")
    instruction: str | None = None
    input_text: str | None = None
    output: str | None = None

    if not isinstance(conversations, list):
        errors.append("missing conversations")
    elif len(conversations) != 2:
        errors.append("conversations must contain exactly 2 messages")
    else:
        user_msg, assistant_msg = conversations
        if not isinstance(user_msg, Mapping):
            errors.append("user conversation must be an object")
        elif user_msg.get("role") != "user":
            errors.append("first conversation role must be user")
        else:
            user_content = user_msg.get("content")
            if not isinstance(user_content, str) or not user_content.strip():
                errors.append("missing user content")
            else:
                before, marker, after = user_content.partition("\n\n用户请求：")
                if not marker:
                    errors.append("user content missing 用户请求 marker")
                else:
                    instruction = before
                    input_text = after
                    if not instruction.strip():
                        errors.append("missing instruction")
                    if not input_text.strip():
                        errors.append("missing input")

        if not isinstance(assistant_msg, Mapping):
            errors.append("assistant conversation must be an object")
        elif assistant_msg.get("role") != "assistant":
            errors.append("second conversation role must be assistant")
        else:
            assistant_content = assistant_msg.get("content")
            if not isinstance(assistant_content, str) or not assistant_content.strip():
                errors.append("missing assistant content")
            else:
                output = assistant_content

    payload: dict[str, Any] | None = None
    if isinstance(output, str) and output.strip():
        try:
            decoded = json.loads(output)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid output json: {exc.msg}")
        else:
            if isinstance(decoded, dict):
                payload = decoded
            else:
                errors.append("output json must be an object")

    label: RouteLabel | None = None
    if payload is not None:
        intent = payload.get("intent")
        if not isinstance(intent, str) or intent not in INTENTS:
            errors.append(f"unknown intent: {intent!r}")

        need_memory = payload.get("need_memory")
        if not isinstance(need_memory, bool):
            errors.append("need_memory must be bool")

        need_tools = payload.get("need_tools")
        if not isinstance(need_tools, bool):
            errors.append("need_tools must be bool")

        tool_scope = payload.get("tool_scope")
        if not isinstance(tool_scope, list) or not all(
            isinstance(item, str) and item in TOOL_SCOPES for item in tool_scope
        ):
            errors.append("tool_scope must be a list of known tool scopes")

        risk_level = payload.get("risk_level")
        if not isinstance(risk_level, str) or risk_level not in RISK_LEVELS:
            errors.append(f"unknown risk_level: {risk_level!r}")

        if (
            isinstance(intent, str)
            and isinstance(need_memory, bool)
            and isinstance(need_tools, bool)
            and isinstance(tool_scope, list)
            and isinstance(risk_level, str)
            and intent in INTENTS
            and risk_level in RISK_LEVELS
            and all(isinstance(item, str) and item in TOOL_SCOPES for item in tool_scope)
        ):
            label = RouteLabel(
                intent=intent,
                need_memory=need_memory,
                need_tools=need_tools,
                tool_scope=list(tool_scope),
                risk_level=risk_level,
            )

    ok = not errors and label is not None
    if ok and isinstance(instruction, str) and isinstance(input_text, str) and label:
        return ParsedTrainingRecord(
            ok=True,
            errors=[],
            record=TrainingRecord(
                instruction=instruction,
                input=input_text,
                label=label,
                source=source,
            ),
        )
    return ParsedTrainingRecord(ok=False, errors=errors)
