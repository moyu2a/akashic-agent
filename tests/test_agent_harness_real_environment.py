from __future__ import annotations

from pathlib import Path

import pytest

from eval.agent_harness.legacy import IntegrationStatus, LegacySourceRecord
from eval.agent_harness.real_environments import (
    classify_real_environment_failure,
    prepare_real_environment,
)
from eval.agent_harness.real_executor import G10ARealExecutorGate
from eval.agent_harness.registry import LegacyAdapterRegistry
from eval.agent_harness.compatibility import CompatibilityStatus


class Auditable:
    def __init__(self, source: LegacySourceRecord) -> None:
        self.source = source

    def audit(self) -> LegacySourceRecord:
        return self.source


def _source(adapter_name: str = "ipc_live") -> LegacySourceRecord:
    return LegacySourceRecord(
        source_name="live_eval_runner",
        source_path="my_md/test_docs/eval_suite/live_eval_runner.py",
        source_commit="df566c9",
        last_modified="2026-08-06",
        compatibility_status=CompatibilityStatus.ADAPTER_REQUIRED,
        integration_status=IntegrationStatus.ADAPTER_PASS,
        execution_mode="ipc_live",
        real_llm=True,
        fake_provider=False,
        main_gate_allowed=False,
        adapter_ready=False,
        adapter_name=adapter_name,
    )


def _authorization(tmp_path: Path):
    gate = G10ARealExecutorGate(LegacyAdapterRegistry([Auditable(_source())]))
    return gate.prepare(
        adapter_name="ipc_live",
        governance_profile="full_governance",
        environment_kind="ipc_live",
        workspace=tmp_path,
        case_id="case-1",
    )


def test_real_environment_creates_isolated_workspace_per_case_and_profile(
    tmp_path: Path,
) -> None:
    auth = _authorization(tmp_path)
    env1 = prepare_real_environment(
        auth,
        run_id="run-1",
        profile_name="budget_limited",
    )
    env2 = prepare_real_environment(
        auth,
        run_id="run-1",
        profile_name="full_governance",
        case_id="case-2",
    )

    assert env1.workspace != env2.workspace
    assert env1.session_key != env2.session_key
    assert env1.sessions_db_path != env2.sessions_db_path
    assert env1.observe_db_path != env2.observe_db_path
    assert env1.memory_db_path != env2.memory_db_path
    assert env1.tool_audit_db_path != env2.tool_audit_db_path
    assert (
        env1.runtime_config["runtime_profile"]["governance_profile"]
        == "full_governance"
    )
    assert env1.runtime_config["runtime_profile"]["task_execution"]["enabled"] is True


def test_real_environment_cleanup_does_not_delete_non_eval_workspace(
    tmp_path: Path,
) -> None:
    auth = _authorization(tmp_path)
    non_eval = tmp_path / "shared.txt"
    non_eval.write_text("keep", encoding="utf-8")
    env = prepare_real_environment(auth, run_id="run-2", profile_name="budget_limited")

    env.cleanup()

    assert non_eval.exists()
    assert env.workspace.exists() is False


def test_real_environment_rejects_default_production_socket(tmp_path: Path) -> None:
    auth = _authorization(tmp_path)

    with pytest.raises(ValueError, match="socket"):
        prepare_real_environment(
            auth,
            run_id="run-3",
            profile_name="budget_limited",
            socket_path=Path("/tmp/akashic.sock"),
        )


def test_real_environment_classifies_stale_socket_as_infra_not_case_failure() -> None:
    classification = classify_real_environment_failure(
        "[Errno 111] Connection refused on stale socket /tmp/akashic.sock"
    )

    assert classification == "infra_stale_socket"
