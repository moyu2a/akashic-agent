from __future__ import annotations

from pathlib import Path

from memory2.eval_sleep_hygiene_provenance import (
    MappingSourceRefResolver,
    ProxySourceRefResolver,
    SessionStoreSourceRefResolver,
    build_source_ref_resolver,
    parse_source_ref_for_fetch,
    parse_source_ref_ids,
)
from session.store import SessionStore


def test_parse_source_ref_ids_matches_fetch_messages_suffix_rules() -> None:
    assert parse_source_ref_ids("cli:local:7#h:abc") == ("cli:local:7",)
    assert parse_source_ref_ids("cli:local:7#profile") == ("cli:local:7",)
    assert parse_source_ref_ids('["cli:local:1","cli:local:2"]#h:def') == (
        "cli:local:1",
        "cli:local:2",
    )
    assert parse_source_ref_ids('"cli:local:3"#tag') == ("cli:local:3",)


def test_parse_source_ref_distinguishes_session_refs_and_malformed_json() -> None:
    session_ref = parse_source_ref_for_fetch("cli:local@post_response")
    malformed = parse_source_ref_for_fetch('["cli:local:1"')

    assert session_ref.parse_ok is True
    assert session_ref.level == "session"
    assert session_ref.session_key == "cli:local"
    assert session_ref.message_ids == ()
    assert session_ref.fetchable_by_id is False
    assert malformed.parse_ok is False
    assert malformed.level == "malformed"
    assert malformed.message_ids == ()


def test_proxy_source_ref_resolver_marks_non_empty_ref_as_proxy_success() -> None:
    evidence = ProxySourceRefResolver().resolve("cli:local:7#h:abc")

    assert evidence.source_ref_available is True
    assert evidence.source_ref_parse_success is True
    assert evidence.source_fetch_success is True
    assert evidence.source_fetch_mode == "proxy"
    assert evidence.source_support_status == "proxy_available"


def test_proxy_source_ref_resolver_keeps_session_ref_parse_status() -> None:
    evidence = ProxySourceRefResolver().resolve("cli:local@post_response")

    assert evidence.source_ref_available is True
    assert evidence.source_ref_parse_success is True
    assert evidence.source_fetch_success is True
    assert evidence.source_fetch_mode == "proxy"
    assert evidence.source_support_status == "proxy_session_available"


def test_mapping_source_ref_resolver_reports_missing_and_supported_refs() -> None:
    resolver = MappingSourceRefResolver(
        {
            "cli:local:1": "用户说喜欢中文回答",
            "cli:local:2": "助手回复确认",
        }
    )

    supported = resolver.resolve(
        '["cli:local:1","cli:local:2"]',
        expected_terms=("中文",),
    )
    missing = resolver.resolve("cli:local:404", expected_terms=("中文",))

    assert supported.source_fetch_success is True
    assert supported.source_support_status == "supported"
    assert missing.source_fetch_success is False
    assert missing.source_support_status == "missing"


def test_mapping_source_ref_resolver_reports_session_refs_as_unfetchable() -> None:
    resolver = MappingSourceRefResolver({"cli:local:1": "用户说喜欢中文回答"})

    evidence = resolver.resolve("cli:local@post_response", expected_terms=("中文",))

    assert evidence.source_ref_parse_success is True
    assert evidence.source_fetch_success is False
    assert evidence.source_support_status == "session_ref_not_fetchable"


def test_session_store_source_ref_resolver_fetches_real_message_ids(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    store.create_session(key="cli:local")
    inserted = store.insert_message(
        "cli:local",
        role="user",
        content="用户说喜欢中文回答",
        ts="2026-07-22T00:00:00+08:00",
        seq=0,
    )
    resolver = SessionStoreSourceRefResolver(store)

    supported = resolver.resolve(str(inserted["id"]), expected_terms=("中文",))
    unsupported = resolver.resolve(str(inserted["id"]), expected_terms=("不存在术语",))
    missing = resolver.resolve("cli:local:404", expected_terms=("中文",))

    assert supported.source_fetch_mode == "session-store"
    assert supported.source_fetch_success is True
    assert supported.source_support_status == "supported"
    assert unsupported.source_fetch_success is True
    assert unsupported.source_support_status == "unsupported"
    assert missing.source_fetch_success is False
    assert missing.source_support_status == "missing"


def test_build_source_ref_resolver_requires_session_db_for_session_store() -> None:
    resolver = build_source_ref_resolver("proxy")
    assert isinstance(resolver, ProxySourceRefResolver)

    try:
        build_source_ref_resolver("session-store")
    except ValueError as exc:
        assert "--session-db is required" in str(exc)
    else:
        raise AssertionError("session-store mode should require a db path")
