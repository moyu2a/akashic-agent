from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from .compatibility import CompatibilityStatus
from .protocol import EpisodeResult, RunManifest, TaskSpec


class ExecutionMode(str, Enum):
    OFFLINE_TRACE = "offline_trace"
    IPC_LIVE = "ipc_live"
    DEEP_LIVE = "deep_live"
    MEMORY_OFFLINE = "memory_offline"
    REAL_LLM = "real_llm"
    REPORT_ADAPTER = "report_adapter"
    EXTERNAL_BENCHMARK = "external_benchmark"
    SHADOW = "shadow"


class IntegrationStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    CONTRACT_PASS = "CONTRACT_PASS"
    ADAPTER_PASS = "ADAPTER_PASS"
    MAIN_GATE_READY = "MAIN_GATE_READY"
    BLOCKED = "BLOCKED"


_MAIN_GATE_EXECUTOR_SPECS = (
    (
        "live_eval_runner",
        "ipc_live",
        ExecutionMode.IPC_LIVE,
        "my_md/test_docs/eval_suite/live_eval_runner.py",
        "df566c9",
    ),
    (
        "deep_live_eval_runner",
        "deep_live",
        ExecutionMode.DEEP_LIVE,
        "my_md/test_docs/eval_suite/deep_live_eval_runner.py",
        "df566c9",
    ),
    (
        "memory_comprehensive_online_eval",
        "memory_online",
        ExecutionMode.REAL_LLM,
        "memory2/eval_comprehensive_online.py",
        "7bb3b06",
    ),
)


def _strict_bool(
    payload: Mapping[str, Any],
    key: str,
    *,
    default: bool,
) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


@dataclass(frozen=True)
class LegacySourceRecord:
    source_name: str
    source_path: str
    source_commit: str
    last_modified: str
    compatibility_status: CompatibilityStatus
    integration_status: IntegrationStatus
    execution_mode: ExecutionMode
    real_llm: bool | None
    fake_provider: bool
    main_gate_allowed: bool
    adapter_name: str | None = None
    report_kind: str = "unknown"
    notes: str = ""
    adapter_ready: bool = False

    def __post_init__(self) -> None:
        for field_name in ("fake_provider", "main_gate_allowed", "adapter_ready"):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")
        if isinstance(self.compatibility_status, str):
            object.__setattr__(
                self,
                "compatibility_status",
                CompatibilityStatus(self.compatibility_status),
            )
        if isinstance(self.integration_status, str):
            object.__setattr__(
                self,
                "integration_status",
                IntegrationStatus(self.integration_status),
            )
        if isinstance(self.execution_mode, str):
            object.__setattr__(
                self,
                "execution_mode",
                ExecutionMode(self.execution_mode),
            )
        if not self.source_name.strip():
            raise ValueError("source_name must not be empty")
        if not self.source_path.strip():
            raise ValueError("source_path must not be empty")
        if not self.source_commit.strip():
            raise ValueError("source_commit must not be empty")
        if self.adapter_ready:
            if self.compatibility_status not in {
                CompatibilityStatus.MATCH,
                CompatibilityStatus.ADAPTER_REQUIRED,
            }:
                raise ValueError(
                    "adapter_ready requires MATCH or ADAPTER_REQUIRED compatibility"
                )
            if self.integration_status not in {
                IntegrationStatus.ADAPTER_PASS,
                IntegrationStatus.MAIN_GATE_READY,
            }:
                raise ValueError(
                    "adapter_ready requires integration_status=ADAPTER_PASS "
                    "or MAIN_GATE_READY"
                )
            if not self.adapter_name:
                raise ValueError("adapter_ready requires adapter_name")
        if self.integration_status is IntegrationStatus.MAIN_GATE_READY:
            if self.compatibility_status not in {
                CompatibilityStatus.MATCH,
                CompatibilityStatus.ADAPTER_REQUIRED,
            }:
                raise ValueError(
                    "MAIN_GATE_READY requires reusable or adapted compatibility"
                )
            if not self.adapter_name:
                raise ValueError("MAIN_GATE_READY requires adapter_name")
            if not self.adapter_ready:
                raise ValueError("MAIN_GATE_READY requires adapter_ready")
            if not self.main_gate_allowed:
                raise ValueError("MAIN_GATE_READY requires main_gate_allowed")
            if self.real_llm is not True or self.fake_provider:
                raise ValueError("MAIN_GATE_READY requires a real provider")
            if not self.is_main_gate_executor():
                raise ValueError("MAIN_GATE_READY requires an approved live adapter")
        if (
            self.main_gate_allowed
            and self.integration_status is not IntegrationStatus.MAIN_GATE_READY
        ):
            raise ValueError(
                "main_gate_allowed requires integration_status=MAIN_GATE_READY"
            )
        if self.fake_provider and self.real_llm is True:
            raise ValueError("fake_provider cannot be true for real_llm source")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["compatibility_status"] = self.compatibility_status.value
        payload["integration_status"] = self.integration_status.value
        payload["execution_mode"] = self.execution_mode.value
        return payload

    def is_main_gate_executor(self) -> bool:
        repo_root = Path(__file__).resolve().parents[2]
        candidate_path = Path(self.source_path)
        if not candidate_path.is_absolute():
            candidate_path = repo_root / candidate_path
        try:
            resolved_path = candidate_path.resolve()
        except OSError:
            return False
        for (
            source_name,
            adapter_name,
            execution_mode,
            expected_path,
            expected_commit,
        ) in _MAIN_GATE_EXECUTOR_SPECS:
            if (
                self.source_name == source_name
                and self.adapter_name == adapter_name
                and self.execution_mode is execution_mode
                and self.source_commit == expected_commit
            ):
                return resolved_path == (repo_root / expected_path).resolve()
        return False

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> LegacySourceRecord:
        return cls(
            source_name=str(payload["source_name"]),
            source_path=str(payload["source_path"]),
            source_commit=str(payload["source_commit"]),
            last_modified=str(payload["last_modified"]),
            compatibility_status=CompatibilityStatus(
                str(payload["compatibility_status"])
            ),
            integration_status=IntegrationStatus(str(payload["integration_status"])),
            adapter_ready=_strict_bool(payload, "adapter_ready", default=False),
            execution_mode=ExecutionMode(str(payload["execution_mode"])),
            real_llm=payload.get("real_llm"),
            fake_provider=_strict_bool(payload, "fake_provider", default=False),
            main_gate_allowed=_strict_bool(
                payload,
                "main_gate_allowed",
                default=False,
            ),
            adapter_name=(
                str(payload["adapter_name"])
                if payload.get("adapter_name") is not None
                else None
            ),
            report_kind=str(payload.get("report_kind", "unknown")),
            notes=str(payload.get("notes", "")),
        )


@dataclass(frozen=True)
class LegacyRunEnvelope:
    source_name: str
    source_version: str
    source_commit: str
    source_run_id: str
    case_id: str
    repeat_index: int
    input_hash: str
    raw_status: str
    raw_report_ref: str | None
    trace_ref: str | None
    execution_mode: ExecutionMode
    real_llm: bool | None
    fake_provider: bool
    metric_provenance: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    infra_error: str | None = None
    adapter_version: str = "agent-harness-v2"

    def __post_init__(self) -> None:
        if self.repeat_index < 0:
            raise ValueError("repeat_index must be non-negative")
        if not self.input_hash:
            raise ValueError("input_hash must not be empty")
        if self.fake_provider and self.real_llm is True:
            raise ValueError("fake_provider cannot be true for real_llm envelope")
        for metric_name, value in self.metrics.items():
            if value == 0 and self.metric_provenance.get(metric_name) in {
                "unavailable",
                "missing",
            }:
                raise ValueError(
                    f"unavailable metric {metric_name} cannot be represented as zero"
                )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["execution_mode"] = self.execution_mode.value
        return payload


@runtime_checkable
class LegacyRunnerAdapter(Protocol):
    source: LegacySourceRecord

    def audit(self) -> LegacySourceRecord: ...

    def load_cases(self, source: Path) -> list[TaskSpec]: ...

    def convert_result(
        self,
        raw_result: object,
        *,
        task: TaskSpec,
        manifest: RunManifest,
    ) -> EpisodeResult: ...

    def convert_events(
        self,
        raw_result: object,
    ) -> tuple[dict[str, object], ...]: ...


def hash_input(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_source_registry(
    records: Sequence[LegacySourceRecord],
) -> tuple[LegacySourceRecord, ...]:
    names = [record.source_name for record in records]
    if len(names) != len(set(names)):
        raise ValueError("source registry contains duplicate source_name")
    for record in records:
        if (
            record.main_gate_allowed
            and record.integration_status is not IntegrationStatus.MAIN_GATE_READY
        ):
            raise ValueError(f"{record.source_name}: main gate source is not ready")
    return tuple(records)


def write_source_registry(
    path: Path,
    records: Sequence[LegacySourceRecord],
    *,
    generated_at: str,
    runner_version: str = "agent-harness-v2",
) -> None:
    normalized = validate_source_registry(records)
    payload = {
        "generated_at": generated_at,
        "runner_version": runner_version,
        "entry_count": len(normalized),
        "entries": [record.to_dict() for record in normalized],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_source_registry(path: Path) -> tuple[LegacySourceRecord, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise ValueError("source registry must contain an entries list")
    declared_count = payload.get("entry_count") if isinstance(payload, dict) else None
    if declared_count is not None:
        if not isinstance(declared_count, int) or isinstance(declared_count, bool):
            raise ValueError("entry_count must be an integer")
        if declared_count != len(entries):
            raise ValueError("entry_count does not match entries length")
    return validate_source_registry(
        tuple(LegacySourceRecord.from_dict(item) for item in entries)
    )
