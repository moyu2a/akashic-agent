from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from session.store import SessionStore


@dataclass(frozen=True)
class ReactRecoveryResult:
    turn_run_id: str
    reason: str


class ReactRecoveryService:
    def __init__(
        self,
        store: SessionStore,
        *,
        worker_id: str,
        lease_seconds: int = 300,
        resume_turn: Callable[[str], None] | None = None,
    ) -> None:
        self._store = store
        self._worker_id = worker_id
        self._lease_seconds = int(lease_seconds)
        self._resume_turn = resume_turn

    def reconcile_startup(
        self,
        *,
        now: datetime,
        limit: int = 100,
    ) -> list[ReactRecoveryResult]:
        results: list[ReactRecoveryResult] = []
        for turn in self._store.list_recoverable_turn_runs(now=now, limit=limit):
            turn_run_id = str(turn["turn_run_id"])
            claimed = self._store.claim_turn_run_for_recovery(
                turn_run_id=turn_run_id,
                worker_id=self._worker_id,
                lease_expires_at=now + timedelta(seconds=self._lease_seconds),
                now=now,
            )
            if not claimed:
                continue
            results.append(self._recover_claimed_turn(turn_run_id, now=now))
        return results

    def _recover_claimed_turn(
        self,
        turn_run_id: str,
        *,
        now: datetime,
    ) -> ReactRecoveryResult:
        turn = self._store.get_turn_run(turn_run_id)
        if turn is None:
            return ReactRecoveryResult(turn_run_id, "turn_missing")
        if turn["status"] == "final_pending":
            self._store.mark_turn_run_completed(turn_run_id=turn_run_id, now=now)
            return ReactRecoveryResult(turn_run_id, "final_completed")

        step = self._current_step(turn_run_id)
        if step is None:
            return ReactRecoveryResult(turn_run_id, "model_retry_pending")

        attempts = self._attempts(str(step["step_id"]))
        succeeded = [attempt for attempt in attempts if attempt["status"] == "succeeded"]
        if succeeded:
            if self._resume_turn is not None:
                self._resume_turn(turn_run_id)
            return ReactRecoveryResult(turn_run_id, "resumed_after_tool_success")

        running = [attempt for attempt in attempts if attempt["status"] == "running"]
        if running:
            attempt = running[0]
            attempt_id = str(attempt["attempt_id"])
            if bool(attempt["side_effect"]) and not bool(attempt["idempotent"]):
                self._store.mark_tool_invocation_blocked(
                    attempt_id=attempt_id,
                    error_code="blocked_side_effect_unknown",
                    now=now,
                )
                self._store.mark_turn_run_blocked(
                    turn_run_id=turn_run_id,
                    blocked_reason="blocked_side_effect_unknown",
                    now=now,
                )
                return ReactRecoveryResult(turn_run_id, "blocked_side_effect_unknown")
            self._store.mark_tool_invocation_pending(
                attempt_id=attempt_id,
                now=now,
            )
            return ReactRecoveryResult(turn_run_id, "tool_retry_pending")

        return ReactRecoveryResult(turn_run_id, "model_retry_pending")

    def _current_step(self, turn_run_id: str) -> dict[str, Any] | None:
        with self._store._lock:  # noqa: SLF001 - recovery store adapter.
            row = self._store._conn.execute(  # noqa: SLF001
                """
                SELECT step_id, turn_run_id, step_no, status,
                       model_input_json, assistant_tool_call_json,
                       tool_result_message_id, assistant_message_id,
                       error_code, created_at, updated_at
                FROM react_steps
                WHERE turn_run_id = ?
                ORDER BY step_no DESC
                LIMIT 1
                """,
                (turn_run_id,),
            ).fetchone()
        return self._store._row_to_react_step(row) if row is not None else None  # noqa: SLF001

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
                ORDER BY created_at ASC, attempt_id ASC
                """,
                (step_id,),
            ).fetchall()
        return [
            self._store._row_to_tool_invocation_attempt(row)  # noqa: SLF001
            for row in rows
        ]
