from __future__ import annotations

import hashlib


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
