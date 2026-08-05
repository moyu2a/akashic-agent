from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import (
    ContentItem,
    FeedbackResult,
    SaveResult,
    SearchResult,
    TagPreference,
)

_TRACKING_QUERY_KEYS = {
    "from",
    "share_medium",
    "share_source",
    "share_tag",
    "spm_id_from",
    "vd_source",
}
_TAG_STATE = {
    0: "normal",
    1: "deprioritized",
    2: "suppressed",
    3: "muted",
}
_TIME_RANGE_DAYS = {
    "24h": 1,
    "last_24h": 1,
    "recent_24h": 1,
    "recent_7d": 7,
    "recent_30d": 30,
}


class ContentLibraryStore:
    """Structured local storage for user-shared content links."""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save_item(
        self,
        *,
        channel: str,
        chat_id: str,
        url: str,
        title: str = "",
        note: str = "",
        summary: str = "",
        tags: list[str] | None = None,
        captured_at: datetime | None = None,
        source: str = "user_shared",
    ) -> SaveResult:
        clean_url = normalize_url(url)
        platform = detect_platform(clean_url)
        clean_tags = normalize_tags(tags or [])
        captured = _iso(captured_at or datetime.now(timezone.utc))

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM content_items
                WHERE channel = ? AND chat_id = ? AND canonical_url = ?
                """,
                (channel, chat_id, clean_url),
            ).fetchone()
            if row is None:
                item_id = f"content_{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """
                    INSERT INTO content_items (
                        id, channel, chat_id, platform, url, canonical_url,
                        title, note, summary, tags_json, captured_at, source,
                        feedback, push_excluded, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                    """,
                    (
                        item_id,
                        channel,
                        chat_id,
                        platform,
                        clean_url,
                        clean_url,
                        title.strip(),
                        note.strip(),
                        summary.strip(),
                        json.dumps(clean_tags, ensure_ascii=False),
                        captured,
                        source,
                        "neutral",
                        captured,
                    ),
                )
                status = "created"
            else:
                item_id = str(row["id"])
                merged_tags = _merge_tags(
                    clean_tags, json.loads(str(row["tags_json"] or "[]"))
                )
                conn.execute(
                    """
                    UPDATE content_items
                    SET platform = ?,
                        url = ?,
                        title = CASE WHEN ? <> '' THEN ? ELSE title END,
                        note = CASE WHEN ? <> '' THEN ? ELSE note END,
                        summary = CASE WHEN ? <> '' THEN ? ELSE summary END,
                        tags_json = ?,
                        captured_at = ?,
                        source = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        platform,
                        clean_url,
                        title.strip(),
                        title.strip(),
                        note.strip(),
                        note.strip(),
                        summary.strip(),
                        summary.strip(),
                        json.dumps(merged_tags, ensure_ascii=False),
                        captured,
                        source,
                        captured,
                        item_id,
                    ),
                )
                status = "updated"
            saved = self._get_item(conn, item_id)
            assert saved is not None
            return SaveResult(status=status, item=saved)

    def search_items(
        self,
        *,
        channel: str,
        chat_id: str,
        query: str = "",
        platform: str = "",
        tags: list[str] | None = None,
        time_range: str = "",
        limit: int = 10,
        now: datetime | None = None,
    ) -> SearchResult:
        rows = self._scope_rows(channel, chat_id)
        query_text = query.strip().casefold()
        wanted_platform = platform.strip().casefold()
        wanted_tags = {tag.casefold() for tag in normalize_tags(tags or [])}
        start = _time_range_start(time_range, now or datetime.now(timezone.utc))
        candidates: list[tuple[int, ContentItem]] = []
        for row in rows:
            item = _row_to_item(row)
            if wanted_platform and item.platform.casefold() != wanted_platform:
                continue
            if start is not None and _parse_iso(item.captured_at) < start:
                continue
            item_tags = {tag.casefold() for tag in item.tags}
            if wanted_tags and not wanted_tags.issubset(item_tags):
                continue
            haystack = " ".join(
                [item.title, item.note, item.summary, item.url, *item.tags]
            ).casefold()
            if query_text and query_text not in haystack:
                continue
            score = _match_score(item, query_text, wanted_tags)
            candidates.append((score, item))

        candidates.sort(key=lambda pair: (pair[0], pair[1].captured_at), reverse=True)
        items = [item for _, item in candidates[: max(1, min(int(limit), 100))]]
        return SearchResult(count=len(items), items=items)

    def list_recent_items(
        self,
        *,
        channel: str,
        chat_id: str,
        hours: int = 24,
        limit: int = 20,
        for_push: bool = False,
        now: datetime | None = None,
    ) -> SearchResult:
        current = now or datetime.now(timezone.utc)
        start = current - timedelta(hours=max(1, min(int(hours), 24 * 365)))
        preferences = self._tag_preferences(channel, chat_id)
        candidates: list[tuple[int, ContentItem]] = []
        for row in self._scope_rows(channel, chat_id):
            item = _row_to_item(row)
            if _parse_iso(item.captured_at) < start:
                continue
            if item.push_excluded:
                continue
            states = [preferences.get(tag.casefold(), "normal") for tag in item.tags]
            if for_push and any(state in {"suppressed", "muted"} for state in states):
                continue
            priority = 1 if "deprioritized" in states else 0
            candidates.append((priority, item))

        candidates.sort(key=lambda pair: (pair[0], pair[1].captured_at), reverse=True)
        if for_push:
            normal = [item for priority, item in candidates if priority == 0]
            deprioritized = [item for priority, item in candidates if priority == 1]
            items = (normal + deprioritized[:1])[: max(1, min(int(limit), 100))]
        else:
            items = [item for _, item in candidates[: max(1, min(int(limit), 100))]]
        return SearchResult(count=len(items), items=items)

    def mark_feedback(
        self,
        *,
        channel: str,
        chat_id: str,
        item_id: str = "",
        tag: str = "",
        feedback: str,
    ) -> FeedbackResult:
        clean_feedback = feedback.strip().casefold()
        if clean_feedback not in {
            "liked",
            "neutral",
            "less_of_this",
            "mute",
            "restore",
        }:
            raise ValueError("unsupported feedback")
        if bool(item_id.strip()) == bool(tag.strip()):
            raise ValueError("exactly one of item_id or tag is required")

        now = _iso(datetime.now(timezone.utc))
        with self._connect() as conn:
            if item_id.strip():
                row = conn.execute(
                    """
                    SELECT * FROM content_items
                    WHERE id = ? AND channel = ? AND chat_id = ?
                    """,
                    (item_id.strip(), channel, chat_id),
                ).fetchone()
                if row is None:
                    raise ValueError("content item not found")
                excluded = clean_feedback in {"less_of_this", "mute"}
                conn.execute(
                    """
                    UPDATE content_items
                    SET feedback = ?, push_excluded = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (clean_feedback, int(excluded), now, item_id.strip()),
                )
                return FeedbackResult(item=self._get_item(conn, item_id.strip()))

            clean_tag = normalize_tags([tag])[0]
            preference_row = conn.execute(
                """
                SELECT * FROM tag_preferences
                WHERE channel = ? AND chat_id = ? AND tag = ?
                """,
                (channel, chat_id, clean_tag.casefold()),
            ).fetchone()
            count = (
                int(preference_row["negative_feedback_count"]) if preference_row else 0
            )
            if clean_feedback == "less_of_this":
                count = min(3, count + 1)
            elif clean_feedback in {"mute"}:
                count = 3
            elif clean_feedback == "restore":
                count = 0
            else:
                raise ValueError("tag feedback must change push preference")
            state = _TAG_STATE[count]
            conn.execute(
                """
                INSERT INTO tag_preferences (
                    channel, chat_id, tag, negative_feedback_count,
                    push_state, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(channel, chat_id, tag) DO UPDATE SET
                    negative_feedback_count = excluded.negative_feedback_count,
                    push_state = excluded.push_state,
                    updated_at = excluded.updated_at
                """,
                (channel, chat_id, clean_tag.casefold(), count, state, now),
            )
            preference = self._get_tag_preference(conn, channel, chat_id, clean_tag)
            assert preference is not None
            return FeedbackResult(tag_preference=preference)

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS content_items (
                    id TEXT PRIMARY KEY,
                    channel TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    url TEXT NOT NULL,
                    canonical_url TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '',
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    captured_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    feedback TEXT NOT NULL DEFAULT 'neutral',
                    push_excluded INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL,
                    UNIQUE(channel, chat_id, canonical_url)
                );
                CREATE INDEX IF NOT EXISTS idx_content_scope_time
                    ON content_items(channel, chat_id, captured_at DESC);
                CREATE TABLE IF NOT EXISTS tag_preferences (
                    channel TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    negative_feedback_count INTEGER NOT NULL DEFAULT 0,
                    push_state TEXT NOT NULL DEFAULT 'normal',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(channel, chat_id, tag)
                );
                """)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _scope_rows(self, channel: str, chat_id: str) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT * FROM content_items
                    WHERE channel = ? AND chat_id = ?
                    """,
                    (channel, chat_id),
                ).fetchall()
            )

    def _tag_preferences(self, channel: str, chat_id: str) -> dict[str, str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT tag, push_state FROM tag_preferences
                WHERE channel = ? AND chat_id = ?
                """,
                (channel, chat_id),
            ).fetchall()
        return {str(row["tag"]).casefold(): str(row["push_state"]) for row in rows}

    @staticmethod
    def _get_item(conn: sqlite3.Connection, item_id: str) -> ContentItem | None:
        row = conn.execute(
            "SELECT * FROM content_items WHERE id = ?", (item_id,)
        ).fetchone()
        return _row_to_item(row) if row is not None else None

    @staticmethod
    def _get_tag_preference(
        conn: sqlite3.Connection,
        channel: str,
        chat_id: str,
        tag: str,
    ) -> TagPreference | None:
        row = conn.execute(
            """
            SELECT * FROM tag_preferences
            WHERE channel = ? AND chat_id = ? AND tag = ?
            """,
            (channel, chat_id, tag.casefold()),
        ).fetchone()
        if row is None:
            return None
        return TagPreference(
            channel=str(row["channel"]),
            chat_id=str(row["chat_id"]),
            tag=str(row["tag"]),
            negative_feedback_count=int(row["negative_feedback_count"]),
            push_state=str(row["push_state"]),
            updated_at=str(row["updated_at"]),
        )


def normalize_url(value: str) -> str:
    raw = value.strip()
    parsed = urlsplit(raw)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("url must be an absolute http(s) URL")
    host = parsed.hostname.casefold() if parsed.hostname else ""
    if not host:
        raise ValueError("url host is required")
    if host.startswith("www."):
        host = host[4:]
    port = parsed.port
    netloc = host
    if port is not None and not (
        (parsed.scheme.casefold() == "http" and port == 80)
        or (parsed.scheme.casefold() == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.casefold() not in _TRACKING_QUERY_KEYS
        and not key.casefold().startswith("utm_")
    ]
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parsed.scheme.casefold(),
            netloc,
            path,
            urlencode(sorted(query)),
            "",
        )
    )


def detect_platform(url: str) -> str:
    host = urlsplit(url).hostname or ""
    host = host.casefold()
    if "bilibili" in host:
        return "bilibili"
    if "xiaohongshu" in host or host.endswith("xhslink.com"):
        return "xiaohongshu"
    if "douyin" in host:
        return "douyin"
    return "generic"


def normalize_tags(tags: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in tags:
        clean = re.sub(r"\s+", " ", str(value)).strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
    return result


def _merge_tags(new_tags: list[str], old_tags: Any) -> list[str]:
    old = old_tags if isinstance(old_tags, list) else []
    return normalize_tags([*new_tags, *(str(tag) for tag in old)])


def _row_to_item(row: sqlite3.Row) -> ContentItem:
    return ContentItem(
        id=str(row["id"]),
        channel=str(row["channel"]),
        chat_id=str(row["chat_id"]),
        platform=str(row["platform"]),
        url=str(row["url"]),
        title=str(row["title"]),
        note=str(row["note"]),
        summary=str(row["summary"]),
        tags=list(json.loads(str(row["tags_json"] or "[]"))),
        captured_at=str(row["captured_at"]),
        source=str(row["source"]),
        feedback=str(row["feedback"]),
        push_excluded=bool(row["push_excluded"]),
    )


def _match_score(item: ContentItem, query: str, tags: set[str]) -> int:
    score = 0
    if query:
        if query in item.title.casefold():
            score += 4
        if query in item.note.casefold():
            score += 3
        if query in item.summary.casefold():
            score += 2
        if any(query in tag.casefold() for tag in item.tags):
            score += 2
        if query in item.url.casefold():
            score += 1
    score += len(tags.intersection({tag.casefold() for tag in item.tags}))
    return score


def _time_range_start(value: str, now: datetime) -> datetime | None:
    clean = value.strip().casefold()
    if clean == "today":
        current = now.astimezone(timezone.utc)
        return current.replace(hour=0, minute=0, second=0, microsecond=0)
    days = _TIME_RANGE_DAYS.get(clean)
    if days is not None:
        return now - timedelta(days=days)
    if clean:
        raise ValueError("unsupported time_range")
    return None


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
