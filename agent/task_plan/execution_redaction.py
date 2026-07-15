from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

_SECRET_KEYS = frozenset(
    {"authorization", "api_key", "apikey", "token", "password", "secret", "cookie"}
)


def redact_execution_arguments(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): (
                "[REDACTED]"
                if str(key).casefold() in _SECRET_KEYS
                else redact_execution_arguments(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [redact_execution_arguments(item) for item in value]
    return value


def hash_execution_arguments(arguments: Mapping[str, Any]) -> str:
    payload = json.dumps(
        arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def bounded_execution_preview(value: object, *, max_chars: int = 512) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= max_chars else text[: max_chars - 3].rstrip() + "..."
