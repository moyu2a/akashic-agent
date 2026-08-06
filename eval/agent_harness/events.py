from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Mapping

_SECRET_KEY = re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization)")
_SECRET_VALUE = re.compile(
    r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*([^\s,;]+)"
)


def sanitize_payload(value: Any, *, key: str = "") -> Any:
    if _SECRET_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {
            str(item_key): sanitize_payload(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [sanitize_payload(item, key=key) for item in value]
    if isinstance(value, tuple):
        return [sanitize_payload(item, key=key) for item in value]
    if isinstance(value, str):
        return _SECRET_VALUE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    return value


def payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class EventRecord:
    run_id: str
    episode_id: str
    event_index: int
    turn_index: int
    timestamp: str
    event_type: str
    component: str
    payload: dict[str, Any]
    payload_hash: str


class EventLedger:
    def __init__(self, *, run_id: str, episode_id: str) -> None:
        self.run_id = run_id
        self.episode_id = episode_id
        self.events: list[EventRecord] = []

    def append(
        self,
        event_type: str,
        component: str,
        payload: Mapping[str, Any],
        *,
        turn_index: int = 0,
    ) -> EventRecord:
        sanitized = sanitize_payload(payload)
        if not isinstance(sanitized, dict):
            raise TypeError("event payload must sanitize to a dict")
        event = EventRecord(
            run_id=self.run_id,
            episode_id=self.episode_id,
            event_index=len(self.events),
            turn_index=turn_index,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            component=component,
            payload=sanitized,
            payload_hash=payload_hash(sanitized),
        )
        self.events.append(event)
        return event


def event_to_dict(event: EventRecord) -> dict[str, Any]:
    return asdict(event)
