from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from .registry import AdapterRegistryEntry, LegacyAdapterRegistry
from .runtime_profiles import RuntimeProfilePatch, resolve_runtime_profile_patch

_REAL_ENVIRONMENT_KINDS = frozenset(
    {"sandbox_real", "ipc_live", "deep_live", "real_llm"}
)


@dataclass(frozen=True)
class G10AExecutionAuthorization:
    entry: AdapterRegistryEntry
    runtime_profile: RuntimeProfilePatch
    environment_kind: str
    workspace: Path
    case_id: str
    manifest_metadata: dict[str, object]


class G10ARealExecutorGate:
    def __init__(self, registry: LegacyAdapterRegistry) -> None:
        self._registry = registry

    def prepare(
        self,
        *,
        adapter_name: str,
        governance_profile: str,
        environment_kind: str,
        workspace: Path,
        case_id: str,
    ) -> G10AExecutionAuthorization:
        normalized_environment = str(environment_kind or "").strip()
        if normalized_environment not in _REAL_ENVIRONMENT_KINDS:
            raise ValueError(
                f"fake or unsupported real executor environment: {environment_kind}"
            )
        entry = self._registry.require_g10a_candidate(adapter_name)
        runtime_profile = resolve_runtime_profile_patch(governance_profile)
        metadata = {
            "adapter_name": entry.adapter_name,
            "case_id": str(case_id),
            "environment_kind": normalized_environment,
            "runtime_profile": asdict(runtime_profile),
            "source": entry.source.to_dict(),
        }
        return G10AExecutionAuthorization(
            entry=entry,
            runtime_profile=runtime_profile,
            environment_kind=normalized_environment,
            workspace=Path(workspace),
            case_id=str(case_id),
            manifest_metadata=metadata,
        )
