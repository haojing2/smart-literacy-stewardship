"""Small async boundary around Spark's OpenAI-compatible chat API."""

from __future__ import annotations

import json
import logging
import re
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
    ) -> str:
        request: dict[str, Any] = {"model": settings.spark_model_id, "messages": messages, "stream": False, "user": settings.spark_user_id}
        if temperature is not None:
            request["temperature"] = temperature
        if max_tokens is not None:
            request["max_tokens"] = max_tokens
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

        if not response.choices:
            raise SparkResponseError("Spark response has no choices")
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            raise SparkResponseError("Spark response content is empty")
        return content.strip()

    async def stream_chat(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        try:
            stream = await self._client.chat.completions.create(
                model=settings.spark_model_id,
                messages=messages,  # type: ignore[arg-type]
                stream=True,
                user=settings.spark_user_id,
            )
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
    ) -> dict[str, Any]:
        content = await self.chat(messages, temperature=0.2)
        try:
            return self._extract_json_object(content)
        except SparkResponseParseError:
            if not repair:
                raise
            repair_messages = [*messages, {"role": "user", "content": "The previous response did not satisfy the JSON contract. Return only one complete JSON object matching the supplied resultSchema; do not include Markdown or explanatory text."}]
            repaired = await self.chat(repair_messages, temperature=0.2)
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
