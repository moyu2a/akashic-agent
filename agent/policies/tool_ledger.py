from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

ToolClass = Literal[
    "discovery",
    "retrieval",
    "evidence_expand",
    "local_file",
    "execution",
    "external_io",
    "memory_write",
    "unknown",
]

_TOOL_CLASS_BY_NAME: dict[str, ToolClass] = {
    "tool_search": "discovery",
    "search_docs": "retrieval",
    "recall_memory": "retrieval",
    "search_messages": "retrieval",
    "fetch_doc_chunk": "evidence_expand",
    "fetch_messages": "evidence_expand",
    "read_file": "local_file",
    "list_dir": "local_file",
    "shell": "execution",
    "memorize": "memory_write",
}


@dataclass(frozen=True)
class ToolResultFacts:
    result_ok: bool = False
    hit_count: int | None = None
    citation_refs: tuple[str, ...] = ()
    chunk_keys: tuple[str, ...] = ()
    terminal_scope: str = ""
    result_has_evidence: bool = False
    result_has_citation: bool = False
    result_error_code: str = ""


@dataclass(frozen=True)
class ToolCallRecord:
    tool_name: str
    tool_class: ToolClass
    args_hash: str
    args_summary: str
    call_index: int
    visible_before_call: bool
    decision_action: str = "allow"
    decision_reason: str = ""
    requested_unlocks: tuple[str, ...] = ()
    unlocked_tools: tuple[str, ...] = ()
    blocked_tools: tuple[str, ...] = ()
    execution_status: str = ""
    result_ok: bool = False
    hit_count: int | None = None
    citation_refs: tuple[str, ...] = ()
    chunk_keys: tuple[str, ...] = ()
    terminal_scope: str = ""
    result_summary: str = ""
    result_text: str = ""
    result_has_evidence: bool = False
    result_has_citation: bool = False
    result_error_code: str = ""


@dataclass
class ToolCallLedger:
    records: list[ToolCallRecord] = field(default_factory=list)

    def add_record(self, record: ToolCallRecord) -> None:
        self.records.append(record)

    def next_call_index(self) -> int:
        return len(self.records) + 1

    def count_tool(self, tool_name: str) -> int:
        return sum(1 for record in self.records if record.tool_name == tool_name)

    def count_class(self, tool_class: ToolClass) -> int:
        return sum(1 for record in self.records if record.tool_class == tool_class)

    def same_args_count(self, tool_name: str, args_hash: str) -> int:
        return sum(
            1
            for record in self.records
            if record.tool_name == tool_name and record.args_hash == args_hash
        )

    def has_successful_retrieval(self) -> bool:
        return any(
            record.tool_class == "retrieval"
            and record.result_ok
            and (record.hit_count or 0) > 0
            for record in self.records
        )

    def has_citation_evidence(self) -> bool:
        return any(record.result_has_citation for record in self.records)

    def summary(self) -> dict[str, object]:
        class_counts = Counter(record.tool_class for record in self.records)
        return {
            "tool_calls": len(self.records),
            "class_counts": dict(sorted(class_counts.items())),
            "has_successful_retrieval": self.has_successful_retrieval(),
            "has_citation_evidence": self.has_citation_evidence(),
        }


def classify_tool_name(tool_name: str) -> ToolClass:
    return _TOOL_CLASS_BY_NAME.get(tool_name, "unknown")


def stable_args_hash(arguments: Mapping[str, Any]) -> str:
    encoded = json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def summarize_args(arguments: Mapping[str, Any], *, max_chars: int = 240) -> str:
    encoded = json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)
    if len(encoded) <= max_chars:
        return encoded
    return encoded[: max_chars - 1] + "..."


def extract_tool_result_facts(tool_name: str, result_text: str) -> ToolResultFacts:
    try:
        payload = json.loads(result_text)
    except (TypeError, ValueError):
        return ToolResultFacts(result_ok=False)
    if not isinstance(payload, dict):
        return ToolResultFacts(result_ok=False)

    result_ok = payload.get("ok") is True
    error_code = str(payload.get("error_code") or "")
    terminal_scope = str(payload.get("terminal_scope") or "")
    hit_count = _as_int(payload.get("hit_count"))
    citations: list[str] = []
    chunk_keys: list[str] = []

    if isinstance(payload.get("hits"), list):
        for item in payload["hits"]:
            if not isinstance(item, dict):
                continue
            _append_str(citations, item.get("citation"))
            _append_str(chunk_keys, item.get("chunk_id"))

    chunk = payload.get("chunk")
    if isinstance(chunk, dict):
        _append_str(citations, chunk.get("citation"))
        _append_str(chunk_keys, chunk.get("chunk_id"))

    result_has_citation = bool(citations)
    result_has_evidence = result_ok and (
        result_has_citation or bool(chunk_keys) or (hit_count or 0) > 0
    )

    return ToolResultFacts(
        result_ok=result_ok,
        hit_count=hit_count,
        citation_refs=tuple(citations),
        chunk_keys=tuple(chunk_keys),
        terminal_scope=terminal_scope,
        result_has_evidence=result_has_evidence,
        result_has_citation=result_has_citation,
        result_error_code=error_code,
    )


def _append_str(target: list[str], value: object) -> None:
    if isinstance(value, str) and value:
        target.append(value)


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None
