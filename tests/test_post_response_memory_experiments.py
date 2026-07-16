from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from memory2.post_response_worker import PostResponseMemoryWorker
from plugins.default_memory.config import MemoryExperimentsConfig
from plugins.default_memory.experiments import MemoryExperimentRunner


class _Provider:
    async def chat(self, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(content='{"topics":[]}')


class _Memorizer:
    def __init__(self) -> None:
        self.superseded: list[list[str]] = []

    def supersede_batch(self, ids: list[str]) -> None:
        self.superseded.append(ids)


class _Retriever:
    async def retrieve(self, *args: object, **kwargs: object) -> list[object]:
        return []


@pytest.mark.asyncio
async def test_post_response_worker_emits_write_value_shadow_trace(tmp_path):
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="shadow"),
    )
    worker = PostResponseMemoryWorker(
        memorizer=_Memorizer(),
        retriever=_Retriever(),
        light_provider=_Provider(),
        light_model="light",
        experiment_runner=runner,
    )

    await worker.run(
        user_msg="请记住我喜欢中文回答",
        agent_response="已记住。",
        tool_chain=[
            {
                "calls": [
                    {
                        "name": "memorize",
                        "arguments": {"summary": "用户明确要求记住：喜欢中文回答"},
                        "result": "ok item_id=mem_1 status=new",
                    }
                ]
            }
        ],
        source_ref="cli:local@post_response",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
    )

    trace_path = tmp_path / "observe" / "memory_experiments.jsonl"
    content = trace_path.read_text(encoding="utf-8")
    assert '"feature_name": "write_value_score"' in content
    assert '"session_key": "cli:local"' in content
    assert '"baseline_written_count": 1' in content
    assert '"written_item_ids": ["mem_1"]' in content
    assert '"policy_allow_count": 1' in content


@pytest.mark.asyncio
async def test_post_response_worker_does_not_emit_trace_when_disabled(tmp_path):
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=False, mode="off"),
    )
    worker = PostResponseMemoryWorker(
        memorizer=_Memorizer(),
        retriever=_Retriever(),
        light_provider=_Provider(),
        light_model="light",
        experiment_runner=runner,
    )

    await worker.run(
        user_msg="请记住我喜欢中文回答",
        agent_response="已记住。",
        tool_chain=[
            {
                "calls": [
                    {
                        "name": "memorize",
                        "arguments": {"summary": "用户明确要求记住：喜欢中文回答"},
                        "result": "ok item_id=mem_1 status=new",
                    }
                ]
            }
        ],
        source_ref="cli:local@post_response",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
    )

    assert (tmp_path / "observe" / "memory_experiments.jsonl").exists() is False


@pytest.mark.asyncio
async def test_post_response_worker_does_not_emit_trace_without_memorize(tmp_path):
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="shadow"),
    )
    worker = PostResponseMemoryWorker(
        memorizer=_Memorizer(),
        retriever=_Retriever(),
        light_provider=_Provider(),
        light_model="light",
        experiment_runner=runner,
    )

    await worker.run(
        user_msg="普通对话",
        agent_response="普通回复",
        tool_chain=[{"calls": [{"name": "read_file", "result": "ok"}]}],
        source_ref="cli:local@post_response",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
    )

    assert (tmp_path / "observe" / "memory_experiments.jsonl").exists() is False


@pytest.mark.asyncio
async def test_post_response_worker_counts_failed_memorize_as_attempt_not_write(
    tmp_path,
):
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="shadow"),
    )
    worker = PostResponseMemoryWorker(
        memorizer=_Memorizer(),
        retriever=_Retriever(),
        light_provider=_Provider(),
        light_model="light",
        experiment_runner=runner,
    )

    await worker.run(
        user_msg="请记住临时测试变量",
        agent_response="没有写入。",
        tool_chain=[
            {
                "calls": [
                    {
                        "name": "memorize",
                        "arguments": {"summary": "临时测试变量，不要写入长期记忆"},
                        "result": '{"ok": false, "error": "denied"}',
                    }
                ]
            }
        ],
        source_ref="cli:local@post_response",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
    )

    content = (tmp_path / "observe" / "memory_experiments.jsonl").read_text(
        encoding="utf-8"
    )
    assert '"attempted_count": 1' in content
    assert '"baseline_written_count": 0' in content
    assert '"failed": 1' in content


@pytest.mark.asyncio
async def test_experiment_failure_does_not_skip_invalidation():
    class _ExplodingRunner:
        def record_write_value_shadow(self, **kwargs: object) -> None:
            raise RuntimeError("trace failed")

    worker = PostResponseMemoryWorker(
        memorizer=_Memorizer(),
        retriever=_Retriever(),
        light_provider=_Provider(),
        light_model="light",
        experiment_runner=_ExplodingRunner(),
    )
    worker._handle_invalidations = AsyncMock(return_value=900)

    await worker.run(
        user_msg="旧规则错了",
        agent_response="收到。",
        tool_chain=[
            {
                "calls": [
                    {
                        "name": "memorize",
                        "arguments": {"summary": "用户明确要求记住：喜欢中文回答"},
                        "result": "ok item_id=mem_1 status=new",
                    }
                ]
            }
        ],
        source_ref="cli:local@post_response",
        session_key="cli:local",
        channel="cli",
        chat_id="local",
    )

    worker._handle_invalidations.assert_awaited_once()
