from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from memory2.eval_sleep_hygiene_cases import (
    SleepHygieneCase,
    build_sleep_hygiene_cases,
)
from session.store import SessionStore


@dataclass(frozen=True)
class SleepHygieneSourceFixture:
    cases: tuple[SleepHygieneCase, ...]
    session_db_path: Path
    expected_status_counts: dict[str, int]


def build_sleep_hygiene_source_fixture(
    db_path: Path,
    *,
    duplicate_groups: int = 6,
    stale_count: int = 6,
    low_value_count: int = 6,
    retained_count: int = 6,
    hard_per_scenario: int = 4,
) -> SleepHygieneSourceFixture:
    cases = build_sleep_hygiene_cases(
        case_set="all",
        duplicate_groups=duplicate_groups,
        stale_count=stale_count,
        low_value_count=low_value_count,
        retained_count=retained_count,
        missing_source_count=0,
        hard_per_scenario=hard_per_scenario,
    )
    adjusted_cases = _assign_source_states(cases)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _reset_fixture_db_if_safe(db_path)
    store = SessionStore(db_path)
    try:
        _write_fixture_messages(store, adjusted_cases)
    finally:
        store.close()
    _mark_fixture_db(db_path)
    return SleepHygieneSourceFixture(
        cases=adjusted_cases,
        session_db_path=db_path,
        expected_status_counts=_expected_status_counts(adjusted_cases),
    )


def _assign_source_states(
    cases: Sequence[SleepHygieneCase],
) -> tuple[SleepHygieneCase, ...]:
    adjusted: list[SleepHygieneCase] = []
    states = (
        "supported",
        "missing",
        "unsupported",
        "session_ref_not_fetchable",
        "parse_failed",
        "missing_source_ref",
    )
    counter = 0
    message_seq = 0
    for case in cases:
        items = []
        for item in case.memory_items:
            state = states[counter % len(states)]
            source_ref = _source_ref_for_state(state, message_seq)
            source_expected_term = f"source-backed-term-{message_seq}"
            items.append(
                {
                    **item,
                    "source_ref": source_ref,
                    "_source_fixture_state": state,
                    "_source_fixture_message_seq": message_seq,
                    "_source_expected_terms": (source_expected_term,),
                }
            )
            counter += 1
            message_seq += 1
        adjusted.append(
            SleepHygieneCase(
                case_id=case.case_id,
                label=case.label,
                memory_items=tuple(items),
                expected_item_ids=case.expected_item_ids,
                case_set=case.case_set,
                scenario=case.scenario,
                expected_item_states=case.expected_item_states,
            )
        )
    return tuple(adjusted)


def _source_ref_for_state(state: str, message_seq: int) -> str:
    message_id = f"cli:local:{message_seq}"
    if state in {"supported", "missing", "unsupported"}:
        return message_id
    if state == "session_ref_not_fetchable":
        return "cli:local@post_response"
    if state == "parse_failed":
        return '["cli:local:broken"'
    return ""


def _reset_fixture_db_if_safe(db_path: Path) -> None:
    if db_path.exists() and not _is_fixture_db(db_path):
        raise ValueError(
            f"refusing to overwrite existing non-fixture session db: {db_path}"
        )
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(db_path) + suffix)
        if candidate.exists():
            candidate.unlink()


def _is_fixture_db(db_path: Path) -> bool:
    return _is_marked_fixture_db(db_path) or _looks_like_legacy_fixture_db(db_path)


def _is_marked_fixture_db(db_path: Path) -> bool:
    try:
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                """
                SELECT value
                FROM sleep_hygiene_source_fixture_meta
                WHERE key = 'fixture_name'
                """
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False
    return row is not None and row[0] == "sleep_hygiene_source_fixture"


def _looks_like_legacy_fixture_db(db_path: Path) -> bool:
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            session_rows = conn.execute("SELECT key FROM sessions").fetchall()
            message_rows = conn.execute("SELECT extra FROM messages").fetchall()
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False
    if not session_rows or {str(row["key"]) for row in session_rows} != {"cli:local"}:
        return False
    if not message_rows:
        return False
    for row in message_rows:
        try:
            extra = json.loads(str(row["extra"] or "{}"))
        except json.JSONDecodeError:
            return False
        if str(extra.get("source_fixture_state") or "") not in {
            "supported",
            "unsupported",
        }:
            return False
    return True


def _mark_fixture_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sleep_hygiene_source_fixture_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO sleep_hygiene_source_fixture_meta (key, value)
            VALUES ('fixture_name', 'sleep_hygiene_source_fixture')
            """
        )
        conn.commit()
    finally:
        conn.close()


def _write_fixture_messages(
    store: SessionStore,
    cases: Sequence[SleepHygieneCase],
) -> None:
    if not store.session_exists("cli:local"):
        store.create_session(key="cli:local")
    for case in cases:
        for item in case.memory_items:
            state = str(item.get("_source_fixture_state") or "")
            if state not in {"supported", "unsupported"}:
                continue
            message_seq = int(item["_source_fixture_message_seq"])
            store.insert_message(
                "cli:local",
                role="user",
                content=_message_content_for_state(item, state),
                ts="2026-07-22T00:00:00+08:00",
                seq=message_seq,
                extra={
                    "source_fixture_state": state,
                    "memory_item_id": str(item["id"]),
                },
            )


def _message_content_for_state(item: dict[str, object], state: str) -> str:
    if state == "supported":
        expected_terms = item.get("_source_expected_terms")
        support_term = ""
        if isinstance(expected_terms, (list, tuple)) and expected_terms:
            support_term = str(expected_terms[0])
        return f"{item.get('summary') or ''}\n{support_term}".strip()
    return "这是一条不支持当前记忆摘要的原始消息，只用于测试 unsupported source。"


def _expected_status_counts(cases: Sequence[SleepHygieneCase]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        evaluated = set(case.evaluated_item_ids())
        for item in case.memory_items:
            if str(item["id"]) not in evaluated:
                continue
            state = str(item.get("_source_fixture_state") or "unknown")
            counts[state] = counts.get(state, 0) + 1
    return counts
