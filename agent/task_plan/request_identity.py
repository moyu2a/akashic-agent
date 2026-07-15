from __future__ import annotations

import hashlib
from uuid import uuid4

from bus.events import InboundMessage


def ensure_task_execution_request_id(msg: InboundMessage) -> str:
    existing = str(msg.metadata.get("_task_execution_request_id") or "").strip()
    if existing:
        return existing
    trusted = str(msg.metadata.get("_transport_request_id") or "").strip()
    request_id = trusted or f"runtime-{uuid4().hex}"
    msg.metadata["_task_execution_request_id"] = request_id
    return request_id


def derive_task_execution_idempotency_key(
    *,
    session_key: str,
    request_id: str,
    task_id: str,
    step_id: str,
    action: str,
) -> str:
    raw = "\x1f".join((session_key, request_id, task_id, step_id, action))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
