"""Small async boundary around Spark's OpenAI-compatible chat API."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import AsyncIterator
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from app.core.config import settings


logger = logging.getLogger(__name__)


class SparkLLMError(RuntimeError):
    """Base exception for failures at the Spark provider boundary."""


class SparkConfigurationError(SparkLLMError):
    pass


class SparkNetworkError(SparkLLMError):
    pass


class SparkProviderError(SparkLLMError):
    """Spark accepted the HTTP request but rejected it at provider level."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        provider_code: str | int | None = None,
        provider_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.provider_code = provider_code
        self.provider_type = provider_type


class SparkTimeoutError(SparkLLMError):
    pass


class SparkResponseError(SparkLLMError):
    pass


class SparkResponseParseError(SparkResponseError):
    pass


class SparkOutputLengthError(SparkResponseError):
    """Spark stopped at its output limit before completing a resource JSON object."""

    def __init__(self, message: str, *, reasoning_tokens: int | None = None) -> None:
        super().__init__(message)
        self.reasoning_tokens = reasoning_tokens


class SparkContractError(SparkResponseError):
    """Spark returned data that violates an application result contract."""

    pass


class SparkLLMClient:
    """Async client with no knowledge of application services or persistence."""

    def __init__(self) -> None:
        if not settings.spark_api_key:
            raise SparkConfigurationError("SPARK_API_KEY is not configured")
        self._client = AsyncOpenAI(
            api_key=settings.spark_api_key,
            base_url=settings.spark_api_base,
            timeout=settings.spark_timeout_seconds,
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        performance_context: dict[str, object] | None = None,
        model_id: str | None = None,
    ) -> str:
        request: dict[str, Any] = {
            "model": model_id or settings.spark_model_id,
            "messages": messages,
            "stream": False,
            "max_tokens": max_tokens or settings.spark_max_tokens,
            "extra_body": {
                "search_disable": True,
                "enable_thinking": False,
            },
        }
        if settings.spark_lora_id:
            request["extra_headers"] = {"lora_id": settings.spark_lora_id}
        if temperature is not None:
            request["temperature"] = temperature
        started_at = time.perf_counter()
        try:
            response = await self._client.chat.completions.create(**request)  # type: ignore[arg-type]
        except APITimeoutError as exc:
            logger.warning("Spark request timed out")
            raise SparkTimeoutError("Spark request timed out") from exc
        except APIConnectionError as exc:
            logger.warning("Spark request failed due to a network error")
            raise SparkNetworkError("Spark request failed due to a network error") from exc
        except APIStatusError as exc:
            raise self._provider_error(exc, operation="request") from exc
        except Exception as exc:
            logger.warning("Unexpected Spark SDK failure: %s", type(exc).__name__)
            raise SparkLLMError("Spark request failed") from exc

        elapsed_ms = round((time.perf_counter() - started_at) * 1000)
        usage = getattr(response, "usage", None)
        completion_details = getattr(usage, "completion_tokens_details", None)
        reasoning_tokens = getattr(completion_details, "reasoning_tokens", None)
        finish_reason = getattr(response.choices[0], "finish_reason", None) if response.choices else None
        logger.info(
            "Spark performance project_id=%s resource_id=%s analysis_batch=%s "
            "retrieved_chunks=%s context_chars=%s "
            "resource_type=%s attempt=%s requested_max_tokens=%s prompt_tokens=%s "
            "reasoning_tokens=%s completion_tokens=%s finish_reason=%s elapsed_ms=%s "
            "normalize_result=%s repair_triggered=%s",
            (performance_context or {}).get("project_id"),
            (performance_context or {}).get("resource_id"),
            (performance_context or {}).get("analysis_batch"),
            (performance_context or {}).get("retrieved_chunks"),
            (performance_context or {}).get("context_chars"),
            (performance_context or {}).get("resource_type"),
            (performance_context or {}).get("attempt", 1),
            request["max_tokens"],
            getattr(usage, "prompt_tokens", None),
            reasoning_tokens,
            getattr(usage, "completion_tokens", None),
            finish_reason,
            elapsed_ms,
            (performance_context or {}).get("normalize_result"),
            bool((performance_context or {}).get("repair_triggered", False)),
        )

        if not response.choices:
            raise SparkResponseError("Spark response has no choices")
        choice = response.choices[0]
        message = choice.message
        content = message.content
        if finish_reason == "length" and (
            not isinstance(content, str)
            or not content.strip()
            or self._looks_like_truncated_json(content)
        ):
            logger.warning(
                "Spark output length exceeded resource_type=%s requested_max_tokens=%s reasoning_tokens=%s",
                (performance_context or {}).get("resource_type"),
                request["max_tokens"],
                reasoning_tokens,
            )
            raise SparkOutputLengthError(
                "Spark output was truncated at the requested token limit",
                reasoning_tokens=reasoning_tokens,
            )
        if not isinstance(content, str) or not content.strip():
            refusal = getattr(message, "refusal", None)
            tool_calls = getattr(message, "tool_calls", None)
            model_extra = getattr(message, "model_extra", None)
            has_reasoning = bool(
                isinstance(model_extra, dict)
                and model_extra.get("reasoning_content")
            )
            finish_reason = getattr(choice, "finish_reason", None)
            logger.warning(
                "Spark returned empty content model=%s finish_reason=%s usage=%s refusal=%s tool_calls=%s has_reasoning=%s",
                getattr(response, "model", None),
                finish_reason,
                getattr(response, "usage", None),
                refusal,
                tool_calls,
                has_reasoning,
            )
            if refusal:
                raise SparkResponseError("Spark declined to generate the requested content")
            if finish_reason == "length":
                raise SparkResponseError("Spark output exceeded max token limit")
            raise SparkResponseError("Spark response content is empty")
        return content.strip()

    async def stream_chat(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        try:
            request: dict[str, Any] = {
                "model": settings.spark_model_id,
                "messages": messages,
                "stream": True,
                "max_tokens": settings.spark_max_tokens,
                "extra_body": {
                    "search_disable": True,
                    "enable_thinking": False,
                },
            }
            if settings.spark_lora_id:
                request["extra_headers"] = {"lora_id": settings.spark_lora_id}
            stream = await self._client.chat.completions.create(**request)  # type: ignore[arg-type]
            received_content = False
            async for chunk in stream:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content
                if content:
                    received_content = True
                    yield content
            if not received_content:
                raise SparkResponseError("Spark stream response content is empty")
        except SparkLLMError:
            raise
        except (APIConnectionError, APITimeoutError) as exc:
            logger.warning("Spark stream failed due to %s", type(exc).__name__)
            raise SparkNetworkError("Spark stream failed due to a network or timeout error") from exc
        except APIStatusError as exc:
            raise self._provider_error(exc, operation="stream") from exc
        except Exception as exc:
            logger.warning("Unexpected Spark streaming SDK failure: %s", type(exc).__name__)
            raise SparkLLMError("Spark stream failed") from exc

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        repair: bool = True,
        performance_context: dict[str, object] | None = None,
        max_tokens: int | None = None,
        model_id: str | None = None,
    ) -> dict[str, Any]:
        content = await self.chat(
            messages, temperature=0.2, max_tokens=max_tokens,
            performance_context=performance_context,
            model_id=model_id,
        )
        try:
            return self._extract_json_object(content)
        except SparkResponseParseError:
            if not repair:
                raise
            repair_messages = [*messages, {"role": "user", "content": "The previous response did not satisfy the JSON contract. Return only one complete JSON object matching the supplied resultSchema; do not include Markdown or explanatory text."}]
            repaired = await self.chat(
                repair_messages,
                temperature=0.2,
                max_tokens=max_tokens,
                performance_context={**(performance_context or {}), "repair_triggered": True},
                model_id=model_id,
            )
            return self._extract_json_object(repaired)

    @staticmethod
    def _extract_json_object(content: str) -> dict[str, Any]:
        """Safely isolate one JSON object, allowing only surrounding prose."""
        cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", content, flags=re.IGNORECASE).strip()
        decoder = json.JSONDecoder()
        for match in re.finditer(r"\{", cleaned):
            try:
                payload, _ = decoder.raw_decode(cleaned[match.start():])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        raise SparkResponseParseError("Spark response does not contain a complete JSON object")

    @classmethod
    def _looks_like_truncated_json(cls, content: str) -> bool:
        try:
            cls._extract_json_object(content)
        except SparkResponseParseError:
            return True
        return False

    @staticmethod
    def _provider_error(exc: APIStatusError, *, operation: str) -> SparkProviderError:
        provider_code: str | int | None = None
        provider_type: str | None = None
        provider_message: str | None = None
        try:
            payload = exc.response.json()
        except Exception:
            payload = None
        if isinstance(payload, dict):
            error = payload.get("error")
            details = error if isinstance(error, dict) else payload
            provider_code = details.get("code")
            provider_type = details.get("type")
            provider_message = details.get("message")
            if not isinstance(provider_message, str):
                provider_message = None
        logger.warning(
            "Spark provider rejected %s http_status=%s provider_code=%s provider_type=%s provider_message=%s",
            operation,
            exc.status_code,
            provider_code,
            provider_type,
            provider_message,
        )
        return SparkProviderError(
            f"Spark provider returned HTTP status {exc.status_code}",
            status_code=exc.status_code,
            provider_code=provider_code,
            provider_type=provider_type,
        )
