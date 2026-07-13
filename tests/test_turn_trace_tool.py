from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.tools.turn_trace import InspectTurnTraceTool
from agent.tracing.turn_trace_query import TurnTraceQueryService
from tests.test_turn_trace_query import _insert_turn, _make_observe_db


@pytest.mark.asyncio
async def test_inspect_turn_trace_returns_structured_tool_counts(tmp_path: Path) -> None:
    db = tmp_path / "observe.db"
    _make_observe_db(db)
    turn_id = _insert_turn(
        db,
        session_key="cli:s1",
        user_msg="source question",
        tool_chain=[
            {"text": "", "calls": [{"name": "read_file", "status": "success", "result": "a"}]},
            {"text": "", "calls": [{"name": "read_file", "status": "success", "result": "b"}]},
        ],
    )
    tool = InspectTurnTraceTool(TurnTraceQueryService(db))

    raw = await tool.execute(_session_key="cli:s1", selector="turn_id", turn_id=turn_id)
    payload = json.loads(raw)

    assert payload["ok"] is True
    assert payload["turn"]["id"] == turn_id
    assert payload["summary"]["real_tools"] == {"read_file": 2}


@pytest.mark.asyncio
async def test_inspect_turn_trace_requires_session_key(tmp_path: Path) -> None:
    tool = InspectTurnTraceTool(TurnTraceQueryService(tmp_path / "observe.db"))

    raw = await tool.execute(selector="previous_completed")
    payload = json.loads(raw)

    assert payload["ok"] is False
    assert payload["error_code"] == "missing_session_context"


def test_inspect_turn_trace_schema_does_not_expose_session_keys(tmp_path: Path) -> None:
    tool = InspectTurnTraceTool(TurnTraceQueryService(tmp_path / "observe.db"))

    schema = tool.to_schema()
    properties = schema["function"]["parameters"]["properties"]

    assert "session_key" not in properties
    assert "_session_key" not in properties
