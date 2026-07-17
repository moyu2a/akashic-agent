from __future__ import annotations

import sqlite3
from pathlib import Path

from memory2.eval_real_samples import (
    collect_real_memory_samples,
    load_memory_items_readonly,
    load_replacements_readonly,
    open_readonly_connection,
    real_sample_to_eval_case,
)
from memory2.eval_runner import run_eval_cases


def _create_memory_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE memory_items (
            id TEXT PRIMARY KEY,
            memory_type TEXT NOT NULL,
            summary TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            embedding TEXT,
            reinforcement INTEGER NOT NULL DEFAULT 1,
            emotional_weight INTEGER NOT NULL DEFAULT 0,
            extra_json TEXT,
            source_ref TEXT,
            happened_at TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE memory_replacements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            old_item_id TEXT NOT NULL,
            old_memory_type TEXT NOT NULL,
            old_summary TEXT NOT NULL,
            old_source_ref TEXT,
            old_happened_at TEXT,
            old_extra_json TEXT,
            new_item_id TEXT NOT NULL,
            new_memory_type TEXT NOT NULL,
            new_summary TEXT NOT NULL,
            new_source_ref TEXT,
            new_happened_at TEXT,
            new_extra_json TEXT,
            relation_type TEXT NOT NULL DEFAULT 'supersede',
            source_ref TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    rows = [
        (
            "m_pref",
            "preference",
            "用户偏好中文回答",
            "h1",
            None,
            2,
            0,
            '{"scope_channel":"cli","scope_chat_id":"local"}',
            "cli:local@post_response",
            None,
            "active",
            "2026-01-01T00:00:00+00:00",
            "2026-01-02T00:00:00+00:00",
        ),
        (
            "m_rule",
            "procedure",
            "回答代码问题时优先给出可运行测试",
            "h2",
            None,
            1,
            0,
            '{"scope_channel":"cli","scope_chat_id":"local"}',
            "cli:local@post_response",
            None,
            "active",
            "2026-01-01T00:00:00+00:00",
            "2026-01-02T00:00:00+00:00",
        ),
        (
            "m_qq",
            "preference",
            "用户在 QQ 会话要求输出更短",
            "h3",
            None,
            1,
            0,
            '{"scope_channel":"qq","scope_chat_id":"local"}',
            "qq:local@post_response",
            None,
            "active",
            "2026-01-01T00:00:00+00:00",
            "2026-01-02T00:00:00+00:00",
        ),
    ]
    con.executemany(
        """
        INSERT INTO memory_items (
            id, memory_type, summary, content_hash, embedding, reinforcement,
            emotional_weight, extra_json, source_ref, happened_at, status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    con.execute(
        """
        INSERT INTO memory_replacements (
            old_item_id, old_memory_type, old_summary, old_source_ref,
            old_happened_at, old_extra_json, new_item_id, new_memory_type,
            new_summary, new_source_ref, new_happened_at, new_extra_json,
            relation_type, source_ref, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "m_old_pref",
            "preference",
            "用户以前偏好英文回答",
            "cli:local@post_response",
            None,
            "{}",
            "m_pref",
            "preference",
            "用户偏好中文回答",
            "cli:local@post_response",
            None,
            '{"scope_channel":"cli","scope_chat_id":"local"}',
            "supersede",
            "cli:local@post_response",
            "2026-01-03T00:00:00+00:00",
        ),
    )
    con.commit()
    con.close()


def test_load_memory_items_readonly_parses_scope_from_extra_json(
    tmp_path: Path,
) -> None:
    memory_db = tmp_path / "workspace" / "memory" / "memory2.db"
    _create_memory_db(memory_db)

    rows = load_memory_items_readonly(memory_db)

    by_id = {row["id"]: row for row in rows}
    assert by_id["m_pref"]["scope_channel"] == "cli"
    assert by_id["m_pref"]["scope_chat_id"] == "local"
    assert by_id["m_pref"]["status"] == "active"


def test_load_replacements_readonly_returns_replacement_edges(tmp_path: Path) -> None:
    memory_db = tmp_path / "workspace" / "memory" / "memory2.db"
    _create_memory_db(memory_db)

    rows = load_replacements_readonly(memory_db)

    assert rows == [
        {
            "old_item_id": "m_old_pref",
            "old_memory_type": "preference",
            "old_summary": "用户以前偏好英文回答",
            "old_source_ref": "cli:local@post_response",
            "old_extra_json": {},
            "new_item_id": "m_pref",
            "new_memory_type": "preference",
            "new_summary": "用户偏好中文回答",
            "new_source_ref": "cli:local@post_response",
            "new_extra_json": {"scope_channel": "cli", "scope_chat_id": "local"},
            "relation_type": "supersede",
            "source_ref": "cli:local@post_response",
        }
    ]


def test_collect_real_memory_samples_groups_real_items_by_category(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _create_memory_db(workspace / "memory" / "memory2.db")

    sample_set = collect_real_memory_samples(workspace, limit_per_category=5)

    assert sample_set.metrics["memory_item_count"] == 3
    assert sample_set.metrics["replacement_count"] == 1
    categories = {sample.category for sample in sample_set.samples}
    assert {"preference", "procedure", "cross_scope", "version_chain"}.issubset(
        categories
    )


def test_limit_zero_does_not_mark_available_sample_types_unavailable(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _create_memory_db(workspace / "memory" / "memory2.db")

    sample_set = collect_real_memory_samples(workspace, limit_per_category=0)

    assert sample_set.samples == ()
    assert sample_set.metrics["memory_item_count"] == 3
    assert sample_set.metrics["cross_scope_sample_unavailable"] == 0
    assert sample_set.metrics["version_chain_sample_unavailable"] == 0


def test_readonly_connection_rejects_writes(tmp_path: Path) -> None:
    memory_db = tmp_path / "workspace" / "memory" / "memory2.db"
    _create_memory_db(memory_db)

    con = open_readonly_connection(memory_db)

    try:
        try:
            con.execute("DELETE FROM memory_items")
        except sqlite3.OperationalError as exc:
            assert "readonly" in str(exc).lower() or "query only" in str(exc).lower()
        else:
            raise AssertionError("read-only connection unexpectedly allowed write")
    finally:
        con.close()


def test_bad_extra_json_is_skipped_and_counted(tmp_path: Path) -> None:
    memory_db = tmp_path / "workspace" / "memory" / "memory2.db"
    _create_memory_db(memory_db)
    con = sqlite3.connect(memory_db)
    con.execute(
        "UPDATE memory_items SET extra_json = ? WHERE id = ?",
        ("{bad-json", "m_pref"),
    )
    con.commit()
    con.close()

    rows = load_memory_items_readonly(memory_db)
    sample_set = collect_real_memory_samples(tmp_path / "workspace", limit_per_category=5)

    assert "m_pref" not in {row["id"] for row in rows}
    assert sample_set.metrics["invalid_extra_json_count"] == 1


def test_missing_tables_and_empty_db_degrade_to_empty_sample_set(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    memory_db = workspace / "memory" / "memory2.db"
    memory_db.parent.mkdir(parents=True, exist_ok=True)
    sqlite3.connect(memory_db).close()

    sample_set = collect_real_memory_samples(workspace, limit_per_category=5)

    assert sample_set.samples == ()
    assert sample_set.metrics["memory_item_count"] == 0
    assert sample_set.metrics["missing_table_count"] >= 1


def test_items_without_scope_are_skipped_and_counted(tmp_path: Path) -> None:
    memory_db = tmp_path / "workspace" / "memory" / "memory2.db"
    _create_memory_db(memory_db)
    con = sqlite3.connect(memory_db)
    con.execute(
        "UPDATE memory_items SET extra_json = ? WHERE id = ?",
        ("{}", "m_rule"),
    )
    con.commit()
    con.close()

    sample_set = collect_real_memory_samples(tmp_path / "workspace", limit_per_category=5)

    assert sample_set.metrics["missing_scope_count"] == 1
    assert all("m_rule" not in sample.should_recall_ids for sample in sample_set.samples)


def test_absent_cross_scope_and_replacements_are_reported_not_fabricated(
    tmp_path: Path,
) -> None:
    memory_db = tmp_path / "workspace" / "memory" / "memory2.db"
    _create_memory_db(memory_db)
    con = sqlite3.connect(memory_db)
    con.execute("DELETE FROM memory_items WHERE id = 'm_qq'")
    con.execute("DELETE FROM memory_replacements")
    con.commit()
    con.close()

    sample_set = collect_real_memory_samples(tmp_path / "workspace", limit_per_category=5)

    assert sample_set.metrics["cross_scope_sample_unavailable"] == 1
    assert sample_set.metrics["replacement_count"] == 0
    assert "cross_scope" not in {sample.category for sample in sample_set.samples}
    assert "version_chain" not in {sample.category for sample in sample_set.samples}


def test_real_sample_to_eval_case_preserves_labels_and_profiles(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _create_memory_db(workspace / "memory" / "memory2.db")
    sample = collect_real_memory_samples(workspace, limit_per_category=5).samples[0]

    case = real_sample_to_eval_case(sample)

    assert case.id == sample.sample_id
    assert case.setup["scope"]["session_key"] == sample.session_key
    assert case.expectations["should_recall_ids"] == list(sample.should_recall_ids)
    assert "off" in case.config_profiles
    assert "all" in case.config_profiles


def test_real_samples_can_run_through_existing_eval_runner(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _create_memory_db(workspace / "memory" / "memory2.db")
    sample_set = collect_real_memory_samples(workspace, limit_per_category=5)
    cases = [real_sample_to_eval_case(sample) for sample in sample_set.samples]

    report = run_eval_cases(cases)

    assert report.metrics["case_count"] == len(cases)
    assert report.metrics["profile_count"] >= len(cases) * 2
    assert "trace_count_by_feature" in report.metrics
