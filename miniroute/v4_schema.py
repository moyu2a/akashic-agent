from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

SCENES: tuple[str, ...] = (
    "chat",
    "memory",
    "profile",
    "task",
    "file",
    "status",
    "content",
    "action",
    "unknown",
)

OPERATIONS: tuple[str, ...] = (
    "answer",
    "query",
    "update",
    "plan",
    "read",
    "save",
    "execute",
    "unknown",
)

REQUEST_MODES: tuple[str, ...] = ("single", "compound")

V4_INSTRUCTION = """你是 MnemoAgent 的轻量场景识别器。只根据当前用户请求和少量状态分类，不要执行请求。

scene 只能是：
chat, memory, profile, task, file, status, content, action, unknown

operation 只能是：
answer, query, update, plan, read, save, execute, unknown

request_mode 只能是：
single, compound

MiniRoute 只判断处理场景，不读取完整记忆、完整历史、工具列表、插件信息或文件内容。
只输出 JSON，字段固定为：scene, operation, request_mode。"""


@dataclass(frozen=True, slots=True)
class V4RouteLabel:
    scene: str
    operation: str
    request_mode: str = "single"

    def __post_init__(self) -> None:
        if self.scene not in SCENES:
            raise ValueError(f"unknown scene: {self.scene}")
        if self.operation not in OPERATIONS:
            raise ValueError(f"unknown operation: {self.operation}")
        if self.request_mode not in REQUEST_MODES:
            raise ValueError(f"unknown request_mode: {self.request_mode}")

    def to_dict(self) -> dict[str, str]:
        return {
            "scene": self.scene,
            "operation": self.operation,
            "request_mode": self.request_mode,
        }


@dataclass(frozen=True, slots=True)
class V4TrainingRecord:
    input: str
    has_active_task: bool
    label: V4RouteLabel
    source: str
    instruction: str = V4_INSTRUCTION

    def to_training_json(self) -> dict[str, object]:
        active = "true" if self.has_active_task else "false"
        return {
            "conversations": [
                {
                    "role": "user",
                    "content": (
                        f"{self.instruction}\n\n"
                        f"当前状态：has_active_task={active}\n"
                        f"用户请求：{self.input}"
                    ),
                },
                {
                    "role": "assistant",
                    "content": json.dumps(
                        self.label.to_dict(),
                        ensure_ascii=False,
                        separators=(", ", ": "),
                    ),
                },
            ]
        }


@dataclass(frozen=True, slots=True)
class ParsedV4TrainingRecord:
    ok: bool
    errors: list[str]
    record: V4TrainingRecord | None = None


def parse_v4_training_record(
    record: Mapping[str, Any], *, source: str = "unknown"
) -> ParsedV4TrainingRecord:
    errors: list[str] = []
    conversations = record.get("conversations")
    user_content = ""
    output = ""
    if not isinstance(conversations, list):
        errors.append("missing conversations")
    elif len(conversations) != 2:
        errors.append("conversations must contain exactly 2 messages")
    else:
        user_msg, assistant_msg = conversations
        if not isinstance(user_msg, Mapping) or user_msg.get("role") != "user":
            errors.append("first conversation role must be user")
        else:
            user_content = str(user_msg.get("content") or "")
        if (
            not isinstance(assistant_msg, Mapping)
            or assistant_msg.get("role") != "assistant"
        ):
            errors.append("second conversation role must be assistant")
        else:
            output = str(assistant_msg.get("content") or "")

    payload: dict[str, Any] | None = None
    if output:
        try:
            decoded = json.loads(output)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid output json: {exc.msg}")
        else:
            if isinstance(decoded, dict):
                payload = decoded
            else:
                errors.append("output json must be an object")
    else:
        errors.append("missing assistant content")

    label: V4RouteLabel | None = None
    if payload is not None:
        for field in ("scene", "operation", "request_mode"):
            if field not in payload:
                errors.append(f"missing field: {field}")
        extra_fields = sorted(set(payload) - {"scene", "operation", "request_mode"})
        if extra_fields:
            errors.append(f"unexpected fields: {', '.join(extra_fields)}")
        scene = payload.get("scene")
        operation = payload.get("operation")
        request_mode = payload.get("request_mode")
        if isinstance(scene, str) and scene not in SCENES:
            errors.append(f"unknown scene: {scene!r}")
        if isinstance(operation, str) and operation not in OPERATIONS:
            errors.append(f"unknown operation: {operation!r}")
        if isinstance(request_mode, str) and request_mode not in REQUEST_MODES:
            errors.append(f"unknown request_mode: {request_mode!r}")
        if (
            isinstance(scene, str)
            and scene in SCENES
            and isinstance(operation, str)
            and operation in OPERATIONS
            and isinstance(request_mode, str)
            and request_mode in REQUEST_MODES
        ):
            label = V4RouteLabel(scene, operation, request_mode)

    has_active_task = "has_active_task=true" in user_content
    _, marker, input_text = user_content.rpartition("用户请求：")
    if not marker:
        errors.append("user content missing 用户请求 marker")
    elif not input_text.strip():
        errors.append("missing input")

    if not errors and label is not None:
        return ParsedV4TrainingRecord(
            ok=True,
            errors=[],
            record=V4TrainingRecord(
                input=input_text.strip(),
                has_active_task=has_active_task,
                label=label,
                source=source,
            ),
        )
    return ParsedV4TrainingRecord(ok=False, errors=errors)
