"""Vendor-neutral embedding facade for future local knowledge-base retrieval."""

from __future__ import annotations

import math
from typing import Protocol

from app.core.config import settings


class EmbeddingError(RuntimeError):
    pass


class EmbeddingConfigurationError(EmbeddingError):
    pass


class EmbeddingResponseError(EmbeddingError):
    pass


class EmbeddingProvider(Protocol):
    """Provider boundary implemented by cloud and local embedding adapters."""

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, query: str) -> list[float]: ...


class OpenAICompatibleEmbeddingProvider:
    """Adapter usable with OpenAI-compatible embedding endpoints.

    This covers providers such as SiliconFlow and OpenAI-compatible Xunfei
    endpoints. A BGE/local adapter can implement :class:`EmbeddingProvider`
    without changing any retrieval-facing code.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.embedding_api_key
        self._base_url = base_url if base_url is not None else settings.embedding_base_url
        self._model = model if model is not None else settings.embedding_model
        self._timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.embedding_timeout_seconds
        )

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._validate_configuration()
        self._validate_texts(texts)
        response = await self._client().embeddings.create(
            model=self._model,
            input=texts,
        )
        vectors = self._extract_vectors(response)
        if len(vectors) != len(texts):
            raise EmbeddingResponseError("Embedding response count does not match input count")
        return vectors

    async def embed_query(self, query: str) -> list[float]:
        self._validate_configuration()
        self._validate_texts([query])
        vectors = await self.embed_documents([query])
        return vectors[0]

    def _client(self):
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise EmbeddingConfigurationError(
                "openai is required for the OpenAI-compatible embedding provider"
            ) from exc
        options: dict[str, object] = {
            "api_key": self._api_key,
            "timeout": self._timeout_seconds,
        }
        if self._base_url:
            options["base_url"] = self._base_url
        return AsyncOpenAI(**options)

    def _validate_configuration(self) -> None:
        if not self._api_key or not self._api_key.strip():
            raise EmbeddingConfigurationError("EMBEDDING_API_KEY is required")
        if not self._model or not self._model.strip():
            raise EmbeddingConfigurationError("EMBEDDING_MODEL is required")
        if self._timeout_seconds <= 0:
            raise EmbeddingConfigurationError(
                "EMBEDDING_TIMEOUT_SECONDS must be greater than zero"
            )

    @staticmethod
    def _validate_texts(texts: list[str]) -> None:
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise EmbeddingError("Embedding input text must be non-empty")

    @staticmethod
    def _extract_vectors(response: object) -> list[list[float]]:
        data = getattr(response, "data", None)
        if not isinstance(data, list):
            raise EmbeddingResponseError("Embedding response has no data list")
        try:
            ordered = sorted(data, key=lambda item: item.index)
            vectors = [[float(value) for value in item.embedding] for item in ordered]
        except (AttributeError, TypeError, ValueError) as exc:
            raise EmbeddingResponseError("Embedding response contains an invalid vector") from exc
        if any(not vector or not all(math.isfinite(value) for value in vector) for vector in vectors):
            raise EmbeddingResponseError("Embedding response contains an invalid vector")
        return vectors


class EmbeddingService:
    """Stable application API; RAG callers never import a vendor SDK."""

    def __init__(self, provider: EmbeddingProvider | None = None) -> None:
        self._provider = provider or self._build_provider()

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._provider.embed_documents(texts)

    async def embed_query(self, query: str) -> list[float]:
        return await self._provider.embed_query(query)

    @staticmethod
    def _build_provider() -> EmbeddingProvider:
        provider_name = settings.embedding_provider.strip().lower()
        if provider_name in {"openai_compatible", "siliconflow", "xfyun"}:
            return OpenAICompatibleEmbeddingProvider()
        raise EmbeddingConfigurationError(
            f"Unsupported EMBEDDING_PROVIDER: {settings.embedding_provider}. "
            "Inject an EmbeddingProvider implementation for local/BGE models."
        )
