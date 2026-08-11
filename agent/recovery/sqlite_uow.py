from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class AttachedSQLiteUnitOfWork:
    def __init__(
        self,
        *,
        sessions_db_path: str | Path,
        task_plans_db_path: str | Path,
        busy_timeout_ms: int = 3000,
    ) -> None:
        self._sessions_db_path = str(sessions_db_path)
        self._task_plans_db_path = str(task_plans_db_path)
        self._busy_timeout_ms = int(busy_timeout_ms)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._sessions_db_path)
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout = {self._busy_timeout_ms}")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "ATTACH DATABASE ? AS task_plans",
            (self._task_plans_db_path,),
        )
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            try:
                conn.execute("DETACH DATABASE task_plans")
            except Exception:
                pass
            conn.close()
