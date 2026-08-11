from __future__ import annotations

import json
from typing import Any

from session.store import SessionStore


class ReactReplayBlocked(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class ReactReplayBuilder:
    def __init__(self, store: SessionStore) -> None:
        self._store = store

    def build_messages(
        self,
        *,
        session_key: str,
        turn_run_id: str,
    ) -> list[dict[str, object]]:
        turn = self._store.get_turn_run(turn_run_id)
        if turn is None or turn["session_key"] != session_key:
            raise ReactReplayBlocked("blocked_replay_turn_missing")

        messages: list[dict[str, object]] = []
        user_message_id = str(turn.get("user_message_id") or "")
        if user_message_id:
            user = self._store.get_message(user_message_id)
            if user is None:
                raise ReactReplayBlocked("blocked_replay_user_message_missing")
            messages.append({"role": "user", "content": user.get("content") or ""})

        for step in self._steps(turn_run_id):
            raw_tool_calls = step.get("assistant_tool_call_json")
            if not raw_tool_calls:
                continue
            tool_calls = self._parse_tool_calls(str(raw_tool_calls))
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": json.dumps(
                                    call["arguments"],
                                    ensure_ascii=False,
                                ),
                            },
                        }
                        for call in tool_calls
                    ],
                }
            )
            valid_ids = {str(call["id"]) for call in tool_calls}
            for attempt in self._attempts(str(step["step_id"])):
                tool_call_id = str(attempt["tool_call_id"] or "")
                if not tool_call_id:
                    raise ReactReplayBlocked("blocked_replay_missing_tool_call_id")
                if tool_call_id not in valid_ids:
                    raise ReactReplayBlocked("blocked_replay_tool_call_mismatch")
                result_message_id = str(attempt["result_message_id"] or "")
                result = self._store.get_message(result_message_id)
                if result is None:
                    raise ReactReplayBlocked("blocked_replay_missing_tool_result")
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": result.get("content") or "",
                    }
                )
        return messages

    def _steps(self, turn_run_id: str) -> list[dict[str, Any]]:
        with self._store._lock:  # noqa: SLF001 - recovery store adapter.
            rows = self._store._conn.execute(  # noqa: SLF001
                """
                SELECT step_id, turn_run_id, step_no, status,
                       model_input_json, assistant_tool_call_json,
                       tool_result_message_id, assistant_message_id,
                       error_code, created_at, updated_at
                FROM react_steps
                WHERE turn_run_id = ?
                ORDER BY step_no ASC
                """,
                (turn_run_id,),
            ).fetchall()
        return [self._store._row_to_react_step(row) for row in rows]  # noqa: SLF001

    def _attempts(self, step_id: str) -> list[dict[str, Any]]:
        with self._store._lock:  # noqa: SLF001 - recovery store adapter.
            rows = self._store._conn.execute(  # noqa: SLF001
                """
                SELECT attempt_id, turn_run_id, step_id, tool_call_id,
                       tool_name, arguments_json, arguments_hash, status,
                       recovery_ref, pollable, idempotent, side_effect,
                       result_message_id, result_preview, error_code,
                       owner_instance_id, lease_expires_at, started_at,
                       finished_at, created_at, updated_at
                FROM tool_invocation_attempts
                WHERE step_id = ?
                  AND status IN ('succeeded', 'recovered')
                ORDER BY created_at ASC, attempt_id ASC
                """,
                (step_id,),
            ).fetchall()
        return [
            self._store._row_to_tool_invocation_attempt(row)  # noqa: SLF001
            for row in rows
        ]

    def _parse_tool_calls(self, raw: str) -> list[dict[str, Any]]:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ReactReplayBlocked("blocked_replay_invalid_tool_call_json") from exc
        if not isinstance(parsed, list):
            raise ReactReplayBlocked("blocked_replay_invalid_tool_call_json")
        calls: list[dict[str, Any]] = []
        for item in parsed:
            if not isinstance(item, dict):
                raise ReactReplayBlocked("blocked_replay_invalid_tool_call_json")
            tool_call_id = str(item.get("id") or "")
            if not tool_call_id:
                raise ReactReplayBlocked("blocked_replay_missing_tool_call_id")
            name = str(item.get("name") or "")
            arguments = item.get("arguments") or {}
            if not isinstance(arguments, dict):
                raise ReactReplayBlocked("blocked_replay_invalid_tool_call_json")
            calls.append(
                {
                    "id": tool_call_id,
                    "name": name,
                    "arguments": arguments,
                }
            )
        return calls
