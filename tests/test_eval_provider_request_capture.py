from __future__ import annotations

import json
from typing import Any

import pytest

from agent.provider import LLMResponse
from memory2.eval_llm_sample import _RecordingProvider


class _NoopProvider:
    async def chat(self, **kwargs: Any) -> LLMResponse:
        return LLMResponse(content="ok", tool_calls=[])


@pytest.mark.asyncio
async def test_recording_provider_snapshots_request_before_later_message_mutation() -> None:
    provider = _RecordingProvider(_NoopProvider())
    messages = [{"role": "user", "content": "question"}]

    await provider.chat(messages=messages, model="fake-model")
    messages.append({"role": "assistant", "content": "late answer"})

    assert provider.requests[0]["messages"] == [{"role": "user", "content": "question"}]


@pytest.mark.asyncio
async def test_recording_provider_sanitizes_secrets_and_callables() -> None:
    provider = _RecordingProvider(_NoopProvider())

    await provider.chat(
        messages=[{"role": "user", "content": "question"}],
        model="fake-model",
        api_key="secret",
        on_content_delta=lambda _: None,
    )

    captured = provider.requests[0]
    captured_text = json.dumps(captured, ensure_ascii=False)
    assert "api_key" not in captured
    assert "on_content_delta" not in captured
    assert "secret" not in captured_text
