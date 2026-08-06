from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from agent.config_models import TaskExecutionConfig

from .governance_profiles import GovernanceProfileSpec, resolve_governance_profile


@dataclass(frozen=True)
class RuntimeProfilePatch:
    governance_profile: str
    task_execution: TaskExecutionConfig
    optimization_profile: str
    metadata: dict[str, object]
    requires_real_executor_fields: tuple[str, ...]


def resolve_runtime_profile_patch(name: str) -> RuntimeProfilePatch:
    spec = resolve_governance_profile(name)
    return RuntimeProfilePatch(
        governance_profile=spec.name,
        task_execution=_task_execution_for(spec),
        optimization_profile="baseline",
        metadata=_metadata_for(spec),
        requires_real_executor_fields=spec.requires_real_executor_fields,
    )


def missing_required_observed_fields(
    patch: RuntimeProfilePatch, observed_fields: Iterable[str]
) -> tuple[str, ...]:
    observed = {str(field) for field in observed_fields}
    return tuple(
        field for field in patch.requires_real_executor_fields if field not in observed
    )


def profile_observation_satisfied(
    patch: RuntimeProfilePatch, observed_fields: Iterable[str]
) -> bool:
    return not missing_required_observed_fields(patch, observed_fields)


def _metadata_for(spec: GovernanceProfileSpec) -> dict[str, object]:
    return {
        "call_budget_enabled": spec.call_budget_enabled,
        "evidence_stop_enabled": spec.evidence_stop_enabled,
        "profile_contract": "g10a_real_executor",
    }


def _task_execution_for(spec: GovernanceProfileSpec) -> TaskExecutionConfig:
    if not spec.task_execution_enabled:
        return TaskExecutionConfig(enabled=False)
    return spec.to_task_execution_config()
