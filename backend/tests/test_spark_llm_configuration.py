import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.assistants.spark_client import SparkLLMClient, SparkOutputLengthError, SparkProviderError
from app.core.config import Settings, settings


def test_default_spark_openai_compatible_contract() -> None:
    fields = Settings.model_fields
    assert fields["spark_api_base"].default == "https://maas-api.cn-huabei-1.xf-yun.com/v2"
    assert fields["spark_model_id"].default == "spark-x2.5-4b"
    assert fields["spark_lora_id"].default is None
    assert fields["spark_max_tokens"].default == 8192
    assert fields["spark_research_analysis_max_tokens"].default == 8192
    assert fields["spark_research_analysis_model_id"].default is None
    assert fields["spark_timeout_seconds"].default == 120.0


def test_chat_and_stream_read_the_same_model_from_settings(monkeypatch) -> None:
    monkeypatch.setattr(settings, "spark_lora_id", None)
    completion = AsyncMock()
    completion.create.side_effect = [
        type("Response", (), {"choices": [type("Choice", (), {"message": type("Message", (), {"content": "ok"})()})()]})(),
        _stream_chunks(),
    ]
    with patch("app.assistants.spark_client.AsyncOpenAI") as client_type:
        client_type.return_value.chat.completions = completion
        client = SparkLLMClient()

        async def exercise_client() -> tuple[str, str]:
            chat_result = await client.chat([{"role": "user", "content": "hello"}])
            stream_result = "".join(
                [
                    item
                    async for item in client.stream_chat(
                        [{"role": "user", "content": "hello"}]
                    )
                ]
            )
            return chat_result, stream_result

        assert asyncio.run(exercise_client()) == ("ok", "stream")

    assert completion.create.await_args_list[0].kwargs["model"] == settings.spark_model_id
    assert completion.create.await_args_list[1].kwargs["model"] == settings.spark_model_id
    assert "extra_headers" not in completion.create.await_args_list[0].kwargs
    assert "extra_headers" not in completion.create.await_args_list[1].kwargs
    assert completion.create.await_args_list[0].kwargs["max_tokens"] == settings.spark_max_tokens
    assert completion.create.await_args_list[1].kwargs["max_tokens"] == settings.spark_max_tokens
    expected_body = {"search_disable": True, "enable_thinking": False}
    assert completion.create.await_args_list[0].kwargs["extra_body"] == expected_body
    assert completion.create.await_args_list[1].kwargs["extra_body"] == expected_body
    assert "user" not in completion.create.await_args_list[0].kwargs
    assert "user" not in completion.create.await_args_list[1].kwargs
    assert client_type.call_args.kwargs["base_url"] == settings.spark_api_base


def test_chat_sends_lora_header_only_when_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "spark_lora_id", "custom-lora")
    completion = AsyncMock()
    completion.create.return_value = type(
        "Response", (),
        {"choices": [type("Choice", (), {"message": type("Message", (), {"content": "ok"})()})()]},
    )()
    with patch("app.assistants.spark_client.AsyncOpenAI") as client_type:
        client_type.return_value.chat.completions = completion
        asyncio.run(SparkLLMClient().chat([{"role": "user", "content": "hello"}]))

    assert completion.create.await_args.kwargs["extra_headers"] == {"lora_id": "custom-lora"}


def test_truncated_length_response_preserves_reasoning_tokens() -> None:
    usage = type("Usage", (), {
        "prompt_tokens": 100,
        "completion_tokens": 8192,
        "completion_tokens_details": type("Details", (), {"reasoning_tokens": 7000})(),
    })()
    response = type("Response", (), {
        "usage": usage,
        "choices": [type("Choice", (), {
            "finish_reason": "length",
            "message": type("Message", (), {"content": '{"title":"cut' })(),
        })()],
    })()
    completion = AsyncMock()
    completion.create.return_value = response
    with patch("app.assistants.spark_client.AsyncOpenAI") as client_type:
        client_type.return_value.chat.completions = completion
        with pytest.raises(SparkOutputLengthError) as caught:
            asyncio.run(SparkLLMClient().chat_json(
                [{"role": "user", "content": "resource"}],
                repair=False,
                max_tokens=8192,
                performance_context={"resource_type": "DISCUSSION"},
            ))

    assert caught.value.reasoning_tokens == 7000


def test_provider_error_preserves_safe_diagnostics() -> None:
    response = type(
        "Response",
        (),
        {"json": lambda self: {"error": {"code": 11200, "type": "AppIdNoAuthError", "message": "not authorized"}}},
    )()
    exc = type("StatusError", (), {"response": response, "status_code": 500})()
    error = SparkLLMClient._provider_error(exc, operation="request")  # type: ignore[arg-type]
    assert isinstance(error, SparkProviderError)
    assert error.status_code == 500
    assert error.provider_code == 11200
    assert error.provider_type == "AppIdNoAuthError"


async def _stream_chunks():
    delta = type("Delta", (), {"content": "stream"})()
    yield type("Chunk", (), {"choices": [type("Choice", (), {"delta": delta})()]})()
