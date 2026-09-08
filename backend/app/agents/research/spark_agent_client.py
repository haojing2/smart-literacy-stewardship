from __future__ import annotations

import asyncio
import json
import math
import re
from dataclasses import dataclass
from typing import Any

from app.agents.research.errors import (
    ResearchAgentConfigurationError,
    ResearchAgentConnectionError,
    ResearchAgentParseError,
    ResearchAgentResponseError,
    ResearchAgentTimeoutError,
)
from app.core.config import settings


@dataclass(frozen=True)
class SparkAgentGeneration:
    content: str
    function_call: dict[str, Any] | None = None


class SparkResearchAgentClient:
    """One-shot adapter for the Spark Assistant WebSocket SDK.

    The SDK's ``generate`` method is synchronous.  Each request constructs its
    own SDK client so no WebSocket session is shared across FastAPI requests.
    """

    def __init__(
        self,
        *,
        app_id: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        agent_url: str | None = None,
        domain: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._app_id = app_id if app_id is not None else settings.spark_assistant_app_id
        self._api_key = api_key if api_key is not None else settings.spark_assistant_api_key
        self._api_secret = api_secret if api_secret is not None else settings.spark_assistant_api_secret
        self._agent_url = agent_url if agent_url is not None else settings.research_agent_url
        self._domain = domain if domain is not None else settings.research_agent_domain
        self._timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.research_agent_timeout_seconds
        )

    async def generate(self, messages: list[dict[str, str]]) -> str:
        self._validate_configuration()
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._generate_sync, messages),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise ResearchAgentTimeoutError("Research Agent request timed out") from exc
        except ResearchAgentConfigurationError:
            raise
        except (ConnectionError, OSError) as exc:
            raise ResearchAgentConnectionError("Research Agent connection failed") from exc
        except ResearchAgentResponseError:
            raise
        except Exception as exc:
            raise ResearchAgentConnectionError("Research Agent request failed") from exc

    async def generate_with_functions(
        self,
        messages: list[dict[str, str]],
        function_definitions: list[dict[str, Any]],
    ) -> SparkAgentGeneration:
        self._validate_configuration()
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    self._generate_with_functions_sync,
                    messages,
                    function_definitions,
                ),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise ResearchAgentTimeoutError("Research Agent request timed out") from exc
        except ResearchAgentConfigurationError:
            raise
        except (ConnectionError, OSError) as exc:
            raise ResearchAgentConnectionError("Research Agent connection failed") from exc
        except ResearchAgentResponseError:
            raise
        except Exception as exc:
            # The SDK exposes WebSocket-specific exception classes that vary by
            # version; never leak one of those implementation details to HTTP.
            raise ResearchAgentConnectionError("Research Agent request failed") from exc

    def _generate_sync(self, messages: list[dict[str, str]]) -> str:
        generation = self._generate_with_functions_sync(messages, [])
        if generation.content.strip():
            return generation.content.strip()
        raise ResearchAgentResponseError("Research Agent response content is empty")

    def _generate_with_functions_sync(
        self,
        messages: list[dict[str, str]],
        function_definitions: list[dict[str, Any]],
    ) -> SparkAgentGeneration:
        ChatSparkLLM, ChatMessage = self._load_sdk()
        spark = ChatSparkLLM(
            spark_api_url=self._agent_url,
            spark_app_id=self._app_id,
            spark_api_key=self._api_key,
            spark_api_secret=self._api_secret,
            spark_llm_domain=self._domain,
            streaming=False,
            request_timeout=max(1, math.ceil(self._timeout_seconds)),
        )
        result = spark.generate(
            [[ChatMessage(role=item["role"], content=item["content"]) for item in messages]],
            function_definition=function_definitions,
        )
        return self._extract_generation(result)

    @staticmethod
    def _load_sdk() -> tuple[Any, Any]:
        try:
            from sparkai.core.messages import ChatMessage
            from sparkai.llm.llm import ChatSparkLLM
        except ImportError as exc:
            raise ResearchAgentConfigurationError(
                "spark_ai_python is not installed for the Research Agent"
            ) from exc
        return ChatSparkLLM, ChatMessage

    def _validate_configuration(self) -> None:
        missing = [
            name
            for name, value in (
                ("SPARK_ASSISTANT_APP_ID", self._app_id),
                ("SPARK_ASSISTANT_API_KEY", self._api_key),
                ("SPARK_ASSISTANT_API_SECRET", self._api_secret),
                ("RESEARCH_AGENT_URL", self._agent_url),
            )
            if not value or not value.strip()
        ]
        if missing:
            raise ResearchAgentConfigurationError(
                f"Research Agent configuration is missing: {', '.join(missing)}"
            )
        if self._timeout_seconds <= 0:
            raise ResearchAgentConfigurationError(
                "RESEARCH_AGENT_TIMEOUT_SECONDS must be greater than zero"
            )

    @staticmethod
    def _extract_generation_text(result: Any) -> str:
        generation = SparkResearchAgentClient._extract_generation(result)
        if generation.content.strip():
            return generation.content.strip()
        raise ResearchAgentResponseError("Research Agent response content is empty")

    @staticmethod
    def _extract_generation(result: Any) -> SparkAgentGeneration:
        """Extract text from SDK LLMResult variants without using ``str(result)``."""
        generations = getattr(result, "generations", None)
        if not isinstance(generations, (list, tuple)) or not generations:
            raise ResearchAgentResponseError("Research Agent response has no generations")
        first_group = generations[0]
        if not isinstance(first_group, (list, tuple)) or not first_group:
            raise ResearchAgentResponseError("Research Agent response has no generation")
        generation = first_group[0]
        candidates = (
            getattr(generation, "text", None),
            getattr(getattr(generation, "message", None), "content", None),
            getattr(generation, "content", None),
        )
        for content in candidates:
            if isinstance(content, str) and content.strip():
                text = content.strip()
                break
        else:
            text = ""
        message = getattr(generation, "message", None)
        additional_kwargs = getattr(message, "additional_kwargs", None) or {}
        raw_function_call = (
            getattr(message, "function_call", None)
            or additional_kwargs.get("function_call")
            or getattr(generation, "function_call", None)
        )
        function_call = SparkResearchAgentClient._normalize_function_call(
            raw_function_call
        )
        if not text and function_call is None:
            raise ResearchAgentResponseError("Research Agent response content is empty")
        return SparkAgentGeneration(content=text, function_call=function_call)

    @staticmethod
    def _normalize_function_call(value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict):
            return value
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return {"name": "", "arguments": value}
            return parsed if isinstance(parsed, dict) else None
        return None

    @staticmethod
    def extract_json_object(content: str) -> dict[str, Any]:
        """Extract exactly one JSON object while tolerating surrounding prose."""
        cleaned = re.sub(
            r"^\s*```(?:json)?\s*|\s*```\s*$", "", content, flags=re.IGNORECASE
        ).strip()
        decoder = json.JSONDecoder()
        for match in re.finditer(r"\{", cleaned):
            try:
                payload, _ = decoder.raw_decode(cleaned[match.start() :])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        raise ResearchAgentParseError(
            "Research Agent response does not contain a complete JSON object"
        )
