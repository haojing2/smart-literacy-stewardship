from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.assistants.spark_client import SparkLLMClient, SparkResponseParseError


def _response(content: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


async def _stream():
    yield SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content="你"))]
    )
    yield SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content="好"))]
    )


def test_chat_json_uses_mocked_async_openai_response() -> None:
    with patch("app.assistants.spark_client.AsyncOpenAI") as client_type:
        completion = AsyncMock(return_value=_response("```json\n{\"ok\": true}\n```"))
        client_type.return_value.chat.completions.create = completion
        with patch("app.assistants.spark_client.settings.spark_api_key", "test-key"):
            result = asyncio.run(SparkLLMClient().chat_json([{"role": "user", "content": "x"}]))
    assert result == {"ok": True}
    assert completion.await_count == 1
    assert completion.await_args.kwargs["stream"] is False
    assert completion.await_args.kwargs["user"] == "123456"
    assert completion.await_args.kwargs["temperature"] == 0.2


def test_stream_chat_yields_only_content() -> None:
    async def collect() -> list[str]:
        with patch("app.assistants.spark_client.AsyncOpenAI") as client_type:
            completion = AsyncMock(return_value=_stream())
            client_type.return_value.chat.completions.create = completion
            with patch("app.assistants.spark_client.settings.spark_api_key", "test-key"):
                return [
                    item
                    async for item in SparkLLMClient().stream_chat(
                        [{"role": "user", "content": "x"}]
                    )
                ]

    assert asyncio.run(collect()) == ["你", "好"]


def test_chat_json_rejects_invalid_json() -> None:
    with patch("app.assistants.spark_client.AsyncOpenAI") as client_type:
        client_type.return_value.chat.completions.create = AsyncMock(return_value=_response("not-json"))
        with patch("app.assistants.spark_client.settings.spark_api_key", "test-key"):
            try:
                asyncio.run(SparkLLMClient().chat_json([{"role": "user", "content": "x"}]))
            except SparkResponseParseError:
                return
    raise AssertionError("invalid JSON must raise SparkResponseParseError")


def test_chat_json_repairs_invalid_response_once() -> None:
    with patch("app.assistants.spark_client.AsyncOpenAI") as client_type:
        completion = AsyncMock(side_effect=[_response("not-json"), _response('{"ok": true}')])
        client_type.return_value.chat.completions.create = completion
        with patch("app.assistants.spark_client.settings.spark_api_key", "test-key"):
            result = asyncio.run(SparkLLMClient().chat_json([{"role": "user", "content": "x"}]))
    assert result == {"ok": True}
    assert completion.await_count == 2
