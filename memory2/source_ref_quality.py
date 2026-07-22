from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Sequence

from memory2.eval_sleep_hygiene_provenance import parse_source_ref_for_fetch


@dataclass(frozen=True)
class SourceRefQualityInput:
    candidate_id: str
    session_key: str
    baseline_source_ref: str
    candidate_message_ids: tuple[str, ...] = ()
    expected_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceRefQualityResult:
    candidate_id: str
    session_key: str
    baseline_source_ref: str
    normalized_source_ref: str
    baseline_parse_ok: bool
    normalized_parse_ok: bool
    baseline_level: str
    normalized_level: str
    candidate_message_ids: tuple[str, ...]
    expected_terms: tuple[str, ...]
    action: str


def message_list_source_ref(message_ids: Sequence[str]) -> str:
    clean_ids = _dedupe(
        str(message_id).strip()
        for message_id in message_ids
        if str(message_id).strip()
    )
    return json.dumps(list(clean_ids), ensure_ascii=False, separators=(",", ":"))


def normalize_source_ref_shadow(
    candidate: SourceRefQualityInput,
) -> SourceRefQualityResult:
    baseline = parse_source_ref_for_fetch(candidate.baseline_source_ref)
    candidate_message_ids = _candidate_message_ids_for_session(
        candidate.candidate_message_ids,
        session_key=candidate.session_key,
    )
    baseline_owned_by_session = _message_ids_belong_to_session(
        baseline.message_ids,
        session_key=candidate.session_key,
    )
    normalized_source_ref = str(candidate.baseline_source_ref or "").strip()
    action = "kept"
    if baseline.fetchable_by_id and baseline_owned_by_session:
        action = "kept_message_level"
    elif candidate_message_ids:
        normalized_source_ref = message_list_source_ref(candidate_message_ids)
        action = "upgraded_to_message_ids"
    elif not normalized_source_ref:
        action = "kept_missing_no_candidate_message_ids"
    else:
        action = "kept_no_candidate_message_ids"
    normalized = parse_source_ref_for_fetch(normalized_source_ref)
    return SourceRefQualityResult(
        candidate_id=candidate.candidate_id,
        session_key=candidate.session_key,
        baseline_source_ref=str(candidate.baseline_source_ref or "").strip(),
        normalized_source_ref=normalized_source_ref,
        baseline_parse_ok=baseline.parse_ok,
        normalized_parse_ok=normalized.parse_ok,
        baseline_level=baseline.level,
        normalized_level=normalized.level,
        candidate_message_ids=candidate_message_ids,
        expected_terms=_expected_terms_tuple(candidate.expected_terms),
        action=action,
    )


def _candidate_message_ids_for_session(
    message_ids: Sequence[str],
    *,
    session_key: str,
) -> tuple[str, ...]:
    prefix = f"{str(session_key).strip()}:"
    clean: list[str] = []
    seen: set[str] = set()
    for raw in message_ids:
        message_id = str(raw or "").strip()
        if not message_id.startswith(prefix):
            continue
        seq = message_id[len(prefix):]
        if not seq.isdigit() or message_id in seen:
            continue
        clean.append(message_id)
        seen.add(message_id)
    return tuple(clean)


def _message_ids_belong_to_session(
    message_ids: Sequence[str],
    *,
    session_key: str,
) -> bool:
    return bool(message_ids) and all(
        _is_message_id_for_session(message_id, session_key=session_key)
        for message_id in message_ids
    )


def _is_message_id_for_session(message_id: object, *, session_key: str) -> bool:
    prefix = f"{str(session_key).strip()}:"
    clean_id = str(message_id or "").strip()
    if not clean_id.startswith(prefix):
        return False
    return clean_id[len(prefix):].isdigit()


def _expected_terms_tuple(expected_terms: Sequence[str]) -> tuple[str, ...]:
    if isinstance(expected_terms, str):
        value = expected_terms.strip()
        return (value,) if value else ()
    return tuple(str(term) for term in expected_terms if str(term).strip())


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return tuple(result)
