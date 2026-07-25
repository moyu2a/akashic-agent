from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


EVAL_CONFIG_PROFILES: tuple[str, ...] = (
    "off",
    "phase1",
    "phase2",
    "phase3",
    "phase4",
    "phase5",
    "all",
)

EVAL_PHASE_TARGETS: tuple[str, ...] = (
    "phase1",
    "phase2a",
    "phase2b",
    "phase3a",
    "phase3b",
    "phase4a",
    "phase4b",
    "phase5",
)

EVAL_CONFIG_MATRIX: dict[str, dict[str, object]] = {
    "off": {"enabled": False, "mode": "off", "flags": {}},
    "phase1": {"enabled": True, "mode": "shadow", "flags": {}},
    "phase2": {
        "enabled": True,
        "mode": "shadow",
        "flags": {"graph_retrieval_enabled": True},
    },
    "phase3": {
        "enabled": True,
        "mode": "shadow",
        "flags": {
            "rerank_shadow_enabled": True,
            "injection_governance_shadow_enabled": True,
        },
    },
    "phase4": {
        "enabled": True,
        "mode": "shadow",
        "flags": {
            "version_chain_shadow_enabled": True,
            "provenance_shadow_enabled": True,
        },
    },
    "phase5": {
        "enabled": True,
        "mode": "shadow",
        "flags": {"sleep_consolidation_shadow_enabled": True},
    },
    "all": {
        "enabled": True,
        "mode": "shadow",
        "flags": {
            "graph_retrieval_enabled": True,
            "rerank_shadow_enabled": True,
            "injection_governance_shadow_enabled": True,
            "version_chain_shadow_enabled": True,
            "provenance_shadow_enabled": True,
            "sleep_consolidation_shadow_enabled": True,
        },
    },
}

_REQUIRED_TOP_LEVEL = (
    "id",
    "title",
    "category",
    "phase_targets",
    "config_profiles",
    "setup",
    "expectations",
)
_REQUIRED_SCOPE = ("session_key", "channel", "chat_id")
_REQUIRED_MEMORY_ITEM = ("id", "memory_type", "summary", "status")
_REQUIRED_REPLACEMENT = ("old_item_id", "new_item_id")


@dataclass(frozen=True)
class EvalCase:
    id: str
    title: str
    category: str
    phase_targets: tuple[str, ...]
    config_profiles: tuple[str, ...]
    setup: dict[str, Any]
    expectations: dict[str, Any]
    source_path: str = ""


def load_eval_case(path: Path) -> EvalCase:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    errors = validate_eval_case_payload(payload, source=str(path))
    if errors:
        raise ValueError("\n".join(errors))
    return EvalCase(
        id=str(payload["id"]),
        title=str(payload["title"]),
        category=str(payload["category"]),
        phase_targets=tuple(str(item) for item in payload["phase_targets"]),
        config_profiles=tuple(str(item) for item in payload["config_profiles"]),
        setup=dict(payload["setup"]),
        expectations=dict(payload["expectations"]),
        source_path=str(path),
    )


def load_eval_cases(root: Path) -> list[EvalCase]:
    return [load_eval_case(path) for path in sorted(root.glob("*.json"))]


def validate_eval_case_payload(
    payload: dict[str, object],
    *,
    source: str = "",
) -> list[str]:
    label = source or "<eval_case>"
    errors: list[str] = []
    for field in _REQUIRED_TOP_LEVEL:
        if field not in payload:
            errors.append(f"{label}: missing required field '{field}'")
    if errors:
        return errors

    errors.extend(_validate_string(payload, "id", label))
    errors.extend(_validate_string(payload, "title", label))
    errors.extend(_validate_string(payload, "category", label))
    errors.extend(_validate_phase_targets(payload.get("phase_targets"), label))
    errors.extend(_validate_config_profiles(payload.get("config_profiles"), label))
    errors.extend(_validate_setup(payload.get("setup"), label))
    errors.extend(_validate_expectations(payload.get("expectations"), label))
    errors.extend(
        _validate_profile_expectations(
            payload.get("expectations"),
            payload.get("config_profiles"),
            label,
        )
    )
    return errors


def _validate_string(
    payload: dict[str, object],
    field: str,
    label: str,
) -> list[str]:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        return [f"{label}: field '{field}' must be a non-empty string"]
    return []


def _validate_phase_targets(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        return [f"{label}: field 'phase_targets' must be a non-empty list"]
    errors: list[str] = []
    for item in value:
        text = str(item)
        if text not in EVAL_PHASE_TARGETS:
            errors.append(f"{label}: unknown phase target '{text}' in 'phase_targets'")
    return errors


def _validate_config_profiles(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        return [f"{label}: field 'config_profiles' must be a non-empty list"]
    errors: list[str] = []
    for item in value:
        text = str(item)
        if text not in EVAL_CONFIG_MATRIX:
            errors.append(
                f"{label}: unknown config profile '{text}' in 'config_profiles'"
            )
    return errors


def _validate_setup(value: object, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label}: field 'setup' must be an object"]
    errors: list[str] = []
    scope = value.get("scope")
    if not isinstance(scope, dict):
        errors.append(f"{label}: setup.scope must be an object")
    else:
        for field in _REQUIRED_SCOPE:
            if not str(scope.get(field) or "").strip():
                errors.append(f"{label}: setup.scope.{field} must be non-empty")
    errors.extend(_validate_memory_items(value.get("memory_items"), label))
    errors.extend(_validate_memory_replacements(value.get("memory_replacements"), label))
    query = value.get("query")
    conversation = value.get("conversation")
    if not str(query or "").strip() and not isinstance(conversation, list):
        errors.append(f"{label}: setup must include non-empty query or conversation list")
    return errors


def _validate_memory_items(value: object, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return [f"{label}: setup.memory_items must be a list"]
    errors: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{label}: setup.memory_items[{index}] must be an object")
            continue
        for field in _REQUIRED_MEMORY_ITEM:
            if not str(item.get(field) or "").strip():
                errors.append(
                    f"{label}: setup.memory_items[{index}].{field} must be non-empty"
                )
    return errors


def _validate_memory_replacements(value: object, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        return [f"{label}: setup.memory_replacements must be a list"]
    errors: list[str] = []
    for index, replacement in enumerate(value):
        if not isinstance(replacement, dict):
            errors.append(
                f"{label}: setup.memory_replacements[{index}] must be an object"
            )
            continue
        for field in _REQUIRED_REPLACEMENT:
            if not str(replacement.get(field) or "").strip():
                errors.append(
                    f"{label}: setup.memory_replacements[{index}].{field} must be non-empty"
                )
    return errors


def _validate_expectations(value: object, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label}: field 'expectations' must be an object"]
    errors: list[str] = []
    for field in (
        "should_recall_ids",
        "should_not_recall_ids",
        "expected_trace_features",
        "expected_metric_keys",
        "profile_expectations",
    ):
        if field not in value:
            errors.append(f"{label}: expectations.{field} is required")
        elif field in {"expected_metric_keys", "profile_expectations"}:
            if not isinstance(value.get(field), dict):
                errors.append(f"{label}: expectations.{field} must be an object")
        elif not isinstance(value.get(field), list):
            errors.append(f"{label}: expectations.{field} must be a list")
    return errors


def _validate_profile_expectations(
    expectations: object,
    config_profiles: object,
    label: str,
) -> list[str]:
    if not isinstance(expectations, dict) or not isinstance(config_profiles, list):
        return []
    profiles = {str(item) for item in config_profiles}
    profile_expectations = expectations.get("profile_expectations")
    if not isinstance(profile_expectations, dict):
        return []
    errors: list[str] = []
    expected_traces = {
        str(item) for item in expectations.get("expected_trace_features", [])
    }
    for profile, profile_payload in profile_expectations.items():
        profile_name = str(profile)
        if profile_name not in profiles:
            errors.append(
                f"{label}: expectations.profile_expectations references undeclared profile '{profile_name}'"
            )
        if not isinstance(profile_payload, dict):
            errors.append(
                f"{label}: expectations.profile_expectations.{profile_name} must be an object"
            )
            continue
        required = {
            str(item) for item in profile_payload.get("required_trace_features", [])
        }
        forbidden = {
            str(item) for item in profile_payload.get("forbidden_trace_features", [])
        }
        metric_keys = profile_payload.get("metric_keys", {})
        if metric_keys and not isinstance(metric_keys, dict):
            errors.append(
                f"{label}: expectations.profile_expectations.{profile_name}.metric_keys must be an object"
            )
            continue
        for feature in set(metric_keys) | required:
            if feature not in expected_traces:
                errors.append(
                    f"{label}: profile '{profile_name}' references unknown trace feature '{feature}'"
                )
        overlap = required & forbidden
        if overlap:
            errors.append(
                f"{label}: profile '{profile_name}' has trace features both required and forbidden: {sorted(overlap)}"
            )
    return errors
