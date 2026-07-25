from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from memory2.provenance_experiments import parse_source_ref
from session.store import SessionStore


@dataclass(frozen=True)
class ParsedSourceRef:
    parse_ok: bool
    level: str
    message_ids: tuple[str, ...] = ()
    session_key: str = ""
    suffix: str = ""
    fetchable_by_id: bool = False


@dataclass(frozen=True)
class SourceRefEvidence:
    source_ref_available: bool
    source_ref_parse_success: bool
    source_fetch_success: bool
    source_fetch_mode: str
    source_support_status: str
    source_support_reason: str = ""


class SourceRefResolver(Protocol):
    def resolve(
        self,
        source_ref: object,
        *,
        expected_terms: Sequence[str] = (),
    ) -> SourceRefEvidence:
        ...


def parse_source_ref_for_fetch(source_ref: object) -> ParsedSourceRef:
    raw = str(source_ref or "").strip()
    prefix, suffix = _split_fetch_suffix(raw)
    try:
        loaded = json.loads(prefix)
    except (json.JSONDecodeError, ValueError):
        loaded = None
    if isinstance(loaded, str) and loaded.strip():
        message_id = loaded.strip()
        return ParsedSourceRef(
            parse_ok=True,
            level="message",
            message_ids=(message_id,),
            suffix=suffix,
            fetchable_by_id=True,
        )

    parsed = parse_source_ref(raw)
    level = str(parsed.get("level") or "")
    message_ids = tuple(str(item) for item in parsed.get("message_ids", []) if str(item))
    session_key = str(parsed.get("session_key") or "")
    parsed_suffix = str(parsed.get("span_or_suffix") or suffix)
    return ParsedSourceRef(
        parse_ok=bool(parsed.get("parse_ok")),
        level=level,
        message_ids=message_ids,
        session_key=session_key,
        suffix=parsed_suffix,
        fetchable_by_id=level == "message" and bool(message_ids),
    )


def parse_source_ref_ids(source_ref: object) -> tuple[str, ...]:
    parsed = parse_source_ref_for_fetch(source_ref)
    if not parsed.fetchable_by_id:
        return ()
    return parsed.message_ids


def _split_fetch_suffix(source_ref: str) -> tuple[str, str]:
    if "#" not in source_ref:
        return source_ref, ""
    base, suffix = source_ref.split("#", 1)
    return base.strip(), suffix.strip()


class ProxySourceRefResolver:
    def resolve(
        self,
        source_ref: object,
        *,
        expected_terms: Sequence[str] = (),
    ) -> SourceRefEvidence:
        available = bool(str(source_ref or "").strip())
        parsed = parse_source_ref_for_fetch(source_ref)
        status = "missing_source_ref"
        if available and parsed.level == "session":
            status = "proxy_session_available"
        elif available and parsed.parse_ok:
            status = "proxy_available"
        elif available:
            status = "parse_failed"
        return SourceRefEvidence(
            source_ref_available=available,
            source_ref_parse_success=parsed.parse_ok if available else False,
            source_fetch_success=available,
            source_fetch_mode="proxy",
            source_support_status=status,
        )


class MappingSourceRefResolver:
    def __init__(self, messages_by_id: Mapping[str, str]) -> None:
        self._messages_by_id = {
            str(key): str(value) for key, value in messages_by_id.items()
        }

    def resolve(
        self,
        source_ref: object,
        *,
        expected_terms: Sequence[str] = (),
    ) -> SourceRefEvidence:
        if not str(source_ref or "").strip():
            return SourceRefEvidence(False, False, False, "mapping", "missing_source_ref")
        parsed = parse_source_ref_for_fetch(source_ref)
        if parsed.level == "session":
            return SourceRefEvidence(
                True,
                parsed.parse_ok,
                False,
                "mapping",
                "session_ref_not_fetchable",
            )
        item_ids = parsed.message_ids if parsed.fetchable_by_id else ()
        if not item_ids:
            return SourceRefEvidence(True, parsed.parse_ok, False, "mapping", "parse_failed")
        messages = [self._messages_by_id.get(item_id) for item_id in item_ids]
        if any(message is None for message in messages):
            return SourceRefEvidence(True, True, False, "mapping", "missing")
        return _support_evidence(
            mode="mapping",
            combined="\n".join(str(message) for message in messages),
            expected_terms=expected_terms,
        )


class SessionStoreSourceRefResolver:
    def __init__(self, store: SessionStore) -> None:
        self._store = store

    def resolve(
        self,
        source_ref: object,
        *,
        expected_terms: Sequence[str] = (),
    ) -> SourceRefEvidence:
        if not str(source_ref or "").strip():
            return SourceRefEvidence(
                False,
                False,
                False,
                "session-store",
                "missing_source_ref",
            )
        parsed = parse_source_ref_for_fetch(source_ref)
        if parsed.level == "session":
            return SourceRefEvidence(
                True,
                parsed.parse_ok,
                False,
                "session-store",
                "session_ref_not_fetchable",
            )
        if not parsed.fetchable_by_id:
            return SourceRefEvidence(
                True,
                parsed.parse_ok,
                False,
                "session-store",
                "parse_failed",
            )
        messages = self._store.fetch_by_ids(list(parsed.message_ids))
        if len(messages) < len(parsed.message_ids):
            return SourceRefEvidence(True, True, False, "session-store", "missing")
        return _support_evidence(
            mode="session-store",
            combined="\n".join(str(message.get("content") or "") for message in messages),
            expected_terms=expected_terms,
        )


def build_source_ref_resolver(
    mode: str,
    *,
    session_db_path: Path | None = None,
) -> SourceRefResolver:
    clean_mode = str(mode or "proxy").strip()
    if clean_mode == "proxy":
        return ProxySourceRefResolver()
    if clean_mode == "session-store":
        if session_db_path is None:
            raise ValueError("--session-db is required when --source-fetch-mode=session-store")
        return SessionStoreSourceRefResolver(SessionStore(session_db_path))
    raise ValueError(f"unsupported source fetch mode: {clean_mode}")


def _support_evidence(
    *,
    mode: str,
    combined: str,
    expected_terms: Sequence[str],
) -> SourceRefEvidence:
    missing_terms = [
        str(term)
        for term in expected_terms
        if str(term).strip() and str(term) not in combined
    ]
    if missing_terms:
        return SourceRefEvidence(
            True,
            True,
            True,
            mode,
            "unsupported",
            source_support_reason="missing_terms:" + ",".join(missing_terms),
        )
    return SourceRefEvidence(True, True, True, mode, "supported")
