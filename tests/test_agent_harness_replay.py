from __future__ import annotations

from pathlib import Path

from eval.agent_harness.events import EventLedger
from eval.agent_harness.replay import load_replay, save_replay, verify_replay


def test_replay_round_trip_and_hash_verification(tmp_path: Path) -> None:
    ledger = EventLedger(run_id="run-001", episode_id="case-001")
    ledger.append("episode_started", "runner", {})
    ledger.append("episode_finished", "runner", {"status": "PASS"})

    path = tmp_path / "replay.json"
    save_replay(path, ledger.events)

    events = load_replay(path)

    assert len(events) == 2
    assert verify_replay(events) is True
