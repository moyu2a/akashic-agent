from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .events import EventRecord, event_to_dict, payload_hash, sanitize_payload


def save_replay(path: Path, events: Iterable[EventRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [event_to_dict(event) for event in events],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def load_replay(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("replay must be a JSON list")
    return [dict(item) for item in payload if isinstance(item, Mapping)]


def verify_replay(events: Iterable[Mapping[str, Any]]) -> bool:
    expected_index = 0
    for event in events:
        if int(event.get("event_index", -1)) != expected_index:
            return False
        payload = sanitize_payload(event.get("payload", {}))
        if not isinstance(payload, dict):
            return False
        if event.get("payload_hash") != payload_hash(payload):
            return False
        expected_index += 1
    return True
