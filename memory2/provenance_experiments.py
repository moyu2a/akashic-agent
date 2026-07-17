from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProvenanceShadowResult:
    baseline_result: dict[str, Any]
    experimental_result: dict[str, Any]
    metrics: dict[str, Any]


def parse_source_ref(source_ref: str) -> dict[str, object]:
    raw = str(source_ref or "").strip()
    if not raw:
        return {"parse_ok": False, "level": "missing", "raw": raw}
    base, suffix = _split_suffix(raw)
    if base.startswith("["):
        message_ids = _parse_message_id_list(base)
        return {
            "parse_ok": bool(message_ids),
            "level": "message" if message_ids else "malformed",
            "raw": raw,
            "message_ids": message_ids,
            "span_or_suffix": suffix,
        }
    if "@post_response" in base:
        session_key = base.split("@", 1)[0].strip()
        return {
            "parse_ok": bool(session_key),
            "level": "session",
            "raw": raw,
            "session_key": session_key,
            "span_or_suffix": suffix,
        }
    if base.count(":") >= 2:
        return {
            "parse_ok": True,
            "level": "message",
            "raw": raw,
            "message_ids": [base],
            "span_or_suffix": suffix,
        }
    if base.count(":") == 1:
        return {
            "parse_ok": True,
            "level": "session",
            "raw": raw,
            "session_key": base,
            "span_or_suffix": suffix,
        }
    return {"parse_ok": False, "level": "malformed", "raw": raw}


def build_provenance_shadow_result(
    *,
    memory_items: list[dict[str, object]],
    recalled_items: list[dict[str, object]],
    scope_channel: str,
    scope_chat_id: str,
) -> ProvenanceShadowResult:
    parsed: list[dict[str, object]] = []
    orphan_ids: list[str] = []
    cross_scope_memory_ids: list[str] = []
    recalled_ids = _ids(recalled_items)
    recalled_by_id = {
        str(item.get("id") or ""): item
        for item in recalled_items
        if str(item.get("id") or "").strip()
    }
    for item in memory_items:
        item_id = str(item.get("id") or "")
        source_ref = str(item.get("source_ref") or "")
        parsed_ref = parse_source_ref(source_ref)
        parsed_ref["item_id"] = item_id
        parsed.append(parsed_ref)
        if not source_ref.strip():
            orphan_ids.append(item_id)
        if _is_cross_scope(
            item,
            scope_channel=scope_channel,
            scope_chat_id=scope_chat_id,
        ):
            cross_scope_memory_ids.append(item_id)

    with_source = [
        item for item in memory_items if str(item.get("source_ref") or "").strip()
    ]
    parseable = [item for item in parsed if bool(item.get("parse_ok"))]
    memory_by_id = {
        str(item.get("id") or ""): item
        for item in memory_items
        if str(item.get("id") or "").strip()
    }
    cross_scope_recalled_ids = [
        item_id
        for item_id in recalled_ids
        if _is_cross_scope(
            memory_by_id.get(item_id, recalled_by_id.get(item_id, {})),
            scope_channel=scope_channel,
            scope_chat_id=scope_chat_id,
        )
    ]
    return ProvenanceShadowResult(
        baseline_result={
            "baseline_recalled_ids": recalled_ids,
            "baseline_recalled_count": len(recalled_ids),
        },
        experimental_result={
            "parsed_source_refs": parsed,
            "orphan_memory_ids": orphan_ids,
            "cross_scope_memory_ids": cross_scope_memory_ids,
            "cross_scope_risk_ids": cross_scope_recalled_ids,
        },
        metrics={
            "source_ref_coverage": _ratio(len(with_source), len(memory_items)),
            "parse_success_rate": _ratio(len(parseable), len(with_source)),
            "source_ref_parse_success_rate": _ratio(
                len(parseable),
                len(with_source),
            ),
            "session_level_source_count": _count_level(parsed, "session"),
            "message_level_source_count": _count_level(parsed, "message"),
            "span_level_source_count": sum(
                1 for item in parsed if str(item.get("span_or_suffix") or "").strip()
            ),
            "malformed_source_ref_count": _count_level(parsed, "malformed"),
            "orphan_memory_count": len(orphan_ids),
            "cross_scope_memory_count": len(cross_scope_memory_ids),
            "cross_scope_risk_count": len(cross_scope_recalled_ids),
        },
    )


def _split_suffix(source_ref: str) -> tuple[str, str]:
    if "#" not in source_ref:
        return source_ref, ""
    base, suffix = source_ref.split("#", 1)
    return base.strip(), suffix.strip()


def _parse_message_id_list(raw: str) -> list[str]:
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [str(item).strip() for item in loaded if str(item).strip()]


def _ids(items: list[dict[str, object]]) -> list[str]:
    result: list[str] = []
    for item in items:
        item_id = str(item.get("id") or "").strip()
        if item_id:
            result.append(item_id)
    return result


def _count_level(parsed: list[dict[str, object]], level: str) -> int:
    return sum(1 for item in parsed if item.get("level") == level)


def _is_cross_scope(
    item: dict[str, object],
    *,
    scope_channel: str,
    scope_chat_id: str,
) -> bool:
    expected_channel = str(scope_channel or "").strip()
    expected_chat_id = str(scope_chat_id or "").strip()
    if not expected_channel and not expected_chat_id:
        return False
    item_channel = str(item.get("scope_channel") or "").strip()
    item_chat_id = str(item.get("scope_chat_id") or "").strip()
    if not item_channel and not item_chat_id:
        return False
    return item_channel != expected_channel or item_chat_id != expected_chat_id


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)
