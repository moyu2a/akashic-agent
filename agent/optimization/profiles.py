from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agent.config_models import OptimizationConfig

OPTIMIZATION_PROFILE_METADATA_KEY = "optimization_profile"
_PROFILE_FALLBACK = "baseline"
_TOOL_RESULT_LIMIT_CHARS = 4_000


@dataclass(frozen=True)
class OptimizationProfileSpec:
    name: str
    simple_fast_path: bool = False
    memory_window: int | None = None
    tool_result_limit_chars: int | None = None


@dataclass(frozen=True)
class ResolvedOptimizationProfile:
    name: str
    enabled: bool
    simple_fast_path: bool
    memory_window: int
    tool_result_limit_chars: int | None
    overrides: dict[str, object]
    requested_profile: str
    source: str


DEFAULT_OPTIMIZATION_PROFILES: dict[str, OptimizationProfileSpec] = {
    "baseline": OptimizationProfileSpec("baseline"),
    "simple_fast_path": OptimizationProfileSpec(
        "simple_fast_path",
        simple_fast_path=True,
    ),
    "context20": OptimizationProfileSpec("context20", memory_window=20),
    "context12": OptimizationProfileSpec("context12", memory_window=12),
    "tool_result_limit": OptimizationProfileSpec(
        "tool_result_limit",
        tool_result_limit_chars=_TOOL_RESULT_LIMIT_CHARS,
    ),
    "combined_p1": OptimizationProfileSpec(
        "combined_p1",
        simple_fast_path=True,
        memory_window=20,
        tool_result_limit_chars=_TOOL_RESULT_LIMIT_CHARS,
    ),
}


def resolve_optimization_profile(
    config: OptimizationConfig | None,
    *,
    base_memory_window: int,
    session_metadata: Mapping[str, object] | None = None,
    msg_metadata: Mapping[str, object] | None = None,
) -> ResolvedOptimizationProfile:
    cfg = config or OptimizationConfig()
    base_window = max(1, int(base_memory_window))
    requested, source = _requested_profile(
        config=cfg,
        session_metadata=session_metadata,
        msg_metadata=msg_metadata,
    )
    if not cfg.enabled:
        return _resolved_baseline(
            base_memory_window=base_window,
            requested_profile=requested,
            source="disabled",
        )

    spec = DEFAULT_OPTIMIZATION_PROFILES.get(requested)
    if spec is None or spec.name == _PROFILE_FALLBACK:
        return _resolved_baseline(
            base_memory_window=base_window,
            requested_profile=requested,
            source=source,
        )

    overrides: dict[str, object] = {}
    if spec.simple_fast_path:
        overrides["simple_fast_path"] = True
    if spec.memory_window is not None:
        overrides["memory_window"] = int(spec.memory_window)
    if spec.tool_result_limit_chars is not None:
        overrides["tool_result_limit_chars"] = int(spec.tool_result_limit_chars)

    return ResolvedOptimizationProfile(
        name=spec.name,
        enabled=True,
        simple_fast_path=bool(spec.simple_fast_path),
        memory_window=int(spec.memory_window or base_window),
        tool_result_limit_chars=(
            int(spec.tool_result_limit_chars)
            if spec.tool_result_limit_chars is not None
            else None
        ),
        overrides=overrides,
        requested_profile=requested,
        source=source,
    )


def available_profile_names() -> tuple[str, ...]:
    return tuple(DEFAULT_OPTIMIZATION_PROFILES.keys())


def is_known_profile(name: str) -> bool:
    return _normalize_profile_name(name) in DEFAULT_OPTIMIZATION_PROFILES


def _requested_profile(
    *,
    config: OptimizationConfig,
    session_metadata: Mapping[str, object] | None,
    msg_metadata: Mapping[str, object] | None,
) -> tuple[str, str]:
    msg_profile = _metadata_profile(msg_metadata)
    if msg_profile:
        return msg_profile, "message"
    session_profile = _metadata_profile(session_metadata)
    if session_profile:
        return session_profile, "session"
    default_profile = _normalize_profile_name(config.default_profile)
    return default_profile or _PROFILE_FALLBACK, "config"


def _metadata_profile(metadata: Mapping[str, object] | None) -> str:
    if not isinstance(metadata, Mapping):
        return ""
    raw = metadata.get(OPTIMIZATION_PROFILE_METADATA_KEY)
    if raw is None:
        raw = metadata.get("usage_profile")
    return _normalize_profile_name(raw)


def _normalize_profile_name(raw: object) -> str:
    text = str(raw or "").strip().lower().replace("-", "_")
    return text


def _resolved_baseline(
    *,
    base_memory_window: int,
    requested_profile: str,
    source: str,
) -> ResolvedOptimizationProfile:
    return ResolvedOptimizationProfile(
        name=_PROFILE_FALLBACK,
        enabled=False,
        simple_fast_path=False,
        memory_window=base_memory_window,
        tool_result_limit_chars=None,
        overrides={},
        requested_profile=requested_profile or _PROFILE_FALLBACK,
        source=source,
    )
