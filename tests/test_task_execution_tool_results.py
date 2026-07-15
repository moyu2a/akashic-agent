from __future__ import annotations

from pathlib import Path

import pytest

from agent.tools.base import ToolResult, normalize_tool_result
from agent.tools.filesystem import ListDirTool, ReadFileTool
from agent.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_read_file_returns_structured_success_for_text(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")

    result = await ReadFileTool(allowed_dir=tmp_path).execute("README.md")

    assert isinstance(result, ToolResult)
    assert result.ok is True
    assert result.error_code == ""
    assert "hello" in result.text


@pytest.mark.asyncio
async def test_read_file_returns_structured_error_for_missing_file(
    tmp_path: Path,
) -> None:
    result = await ReadFileTool(allowed_dir=tmp_path).execute("missing.txt")

    assert isinstance(result, ToolResult)
    assert result.ok is False
    assert result.error_code == "file_not_found"
    assert "文件不存在" in result.text


@pytest.mark.asyncio
async def test_read_file_invalid_range_is_a_structured_error(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")

    result = await ReadFileTool(allowed_dir=tmp_path).execute(
        "README.md", offset="not-an-integer"
    )

    assert isinstance(result, ToolResult)
    assert result.ok is False
    assert result.error_code == "invalid_read_range"


@pytest.mark.asyncio
async def test_list_dir_returns_structured_outcomes(tmp_path: Path) -> None:
    (tmp_path / "child.txt").write_text("x", encoding="utf-8")

    success = await ListDirTool(allowed_dir=tmp_path).execute(".")
    missing = await ListDirTool(allowed_dir=tmp_path).execute("missing")

    assert isinstance(success, ToolResult)
    assert success.ok is True
    assert "child.txt" in success.text
    assert isinstance(missing, ToolResult)
    assert missing.ok is False
    assert missing.error_code == "directory_not_found"


@pytest.mark.asyncio
async def test_legacy_string_result_has_unknown_business_outcome() -> None:
    registry = ToolRegistry()
    registry.register(ListDirTool())

    result = await registry.execute("list_dir", {"path": "/missing"})

    assert isinstance(result, ToolResult)
    assert result.ok is False
    assert result.error_code == "directory_not_found"


def test_legacy_string_result_remains_business_outcome_unknown() -> None:
    result = normalize_tool_result("legacy output")

    assert result.ok is None
    assert result.error_code == ""
