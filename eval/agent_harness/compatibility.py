from __future__ import annotations

from enum import Enum
from typing import Any, Mapping


class CompatibilityStatus(str, Enum):
    MATCH = "MATCH"
    ADAPTER_REQUIRED = "ADAPTER_REQUIRED"
    STALE = "STALE"
    DO_NOT_REUSE = "DO_NOT_REUSE"


def build_compatibility_report(
    entries: list[Mapping[str, Any]],
) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        component = str(entry.get("component", "")).strip()
        commit = str(entry.get("commit", "")).strip()
        status_value = str(entry.get("status", "")).strip()
        if not component or not commit:
            raise ValueError("component and commit are required")
        try:
            status = CompatibilityStatus(status_value)
        except ValueError as exc:
            raise ValueError(
                f"unsupported compatibility status: {status_value}"
            ) from exc
        normalized.append(
            {
                "component": component,
                "commit": commit,
                "status": status.value,
                "reason": str(entry.get("reason", "")).strip(),
                "reusable": status is CompatibilityStatus.MATCH,
            }
        )
    return {
        "entry_count": len(normalized),
        "entries": normalized,
        "main_gate_ready": bool(normalized)
        and all(
            item["status"] == CompatibilityStatus.MATCH.value for item in normalized
        ),
    }
