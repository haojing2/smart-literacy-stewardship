"""Vendor-neutral embedding facade for future local knowledge-base retrieval."""

from __future__ import annotations

import asyncio
import base64
import binascii
from datetime import datetime, timezone
from email.utils import format_datetime
import hashlib
import hmac
import json
import logging
import math
from time import perf_counter
from typing import Any, Protocol
from urllib.parse import urlencode, urlsplit, urlunsplit

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)


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

    This covers providers such as SiliconFlow and other OpenAI-compatible
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


class XfyunNativeEmbeddingProvider:
    """Native Xfyun Embedding HTTP/HMAC adapter.

    The provider intentionally owns all Xfyun-specific authentication,
    ``para``/``query`` domain selection, concurrency, and wire decoding.
    """

    _RETRY_DELAYS_SECONDS = (0.5, 1.0, 2.0)

    def __init__(
        self,
        *,
        app_id: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        url: str | None = None,
        dimension: int | None = None,
        max_concurrency: int | None = None,
        uid: str | None = None,
        timeout_seconds: float | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._app_id = (
            settings.xfyun_embedding_app_id if app_id is None else app_id
        )
        self._api_key = (
            settings.xfyun_embedding_api_key if api_key is None else api_key
        )
        self._api_secret = (
            settings.xfyun_embedding_api_secret
            if api_secret is None
            else api_secret
        )
        self._url = settings.xfyun_embedding_url if url is None else url
        self._dimension = (
            settings.xfyun_embedding_dimension
            if dimension is None
            else dimension
        )
        self._max_concurrency = (
            settings.xfyun_embedding_max_concurrency
            if max_concurrency is None
            else max_concurrency
        )
        self._uid = settings.xfyun_embedding_uid if uid is None else uid
        self._timeout_seconds = (
            settings.embedding_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        self._client = client
        # Configuration is deliberately validated on first use, not while the
        # FastAPI settings/module graph is imported.
        self._semaphore: asyncio.Semaphore | None = None

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._validate_configuration()
        self._validate_texts(texts)
        return list(
            await asyncio.gather(
                *(self._embed_one(text, domain="para") for text in texts)
            )
        )

    async def embed_query(self, query: str) -> list[float]:
        self._validate_configuration()
        self._validate_texts([query])
        return await self._embed_one(query, domain="query")

    async def _embed_one(self, text: str, *, domain: str) -> list[float]:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrency)
        async with self._semaphore:
            started = perf_counter()
            try:
                response = await self._post_with_retry(
                    body=self._build_request_body(text=text, domain=domain),
                    domain=domain,
                )
                return self._parse_response(response)
            finally:
                logger.info(
                    "Embedding request provider=xfyun_native dimension=%s domain=%s duration_ms=%s",
                    self._dimension,
                    domain,
                    round((perf_counter() - started) * 1000),
                )

    async def _post_with_retry(
        self, *, body: dict[str, object], domain: str
    ) -> httpx.Response:
        for attempt in range(len(self._RETRY_DELAYS_SECONDS) + 1):
            try:
                response = await self._post(
                    url=self._authenticated_url(),
                    body=body,
                )
            except httpx.RequestError as exc:
                if attempt >= len(self._RETRY_DELAYS_SECONDS):
                    raise EmbeddingResponseError(
                        "Xfyun Embedding network request failed"
                    ) from exc
                logger.warning(
                    "Embedding retry provider=xfyun_native domain=%s retry=%s reason=network",
                    domain,
                    attempt + 1,
                )
                await asyncio.sleep(self._RETRY_DELAYS_SECONDS[attempt])
                continue

            if response.status_code == 429 or response.status_code >= 500:
                if attempt < len(self._RETRY_DELAYS_SECONDS):
                    logger.warning(
                        "Embedding retry provider=xfyun_native domain=%s http_status=%s retry=%s",
                        domain,
                        response.status_code,
                        attempt + 1,
                    )
                    await asyncio.sleep(self._RETRY_DELAYS_SECONDS[attempt])
                    continue
            if response.status_code < 200 or response.status_code >= 300:
                raise EmbeddingResponseError(
                    f"Xfyun Embedding HTTP request failed with status {response.status_code}"
                )
            return response
        raise EmbeddingResponseError("Xfyun Embedding request failed")

    async def _post(
        self, *, url: str, body: dict[str, object]
    ) -> httpx.Response:
        if self._client is not None:
            return await self._client.post(url, json=body)
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=False,
        ) as client:
            return await client.post(url, json=body)

    def _authenticated_url(self, *, now: datetime | None = None) -> str:
        parsed = urlsplit(self._url)
        host = parsed.netloc
        path = parsed.path or "/"
        date = format_datetime(now or datetime.now(timezone.utc), usegmt=True)
        signature_origin = f"host: {host}\ndate: {date}\nPOST {path} HTTP/1.1"
        signature = base64.b64encode(
            hmac.new(
                self._api_secret.encode("utf-8"),
                signature_origin.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()
        ).decode("ascii")
        authorization_origin = (
            f'api_key="{self._api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature}"'
        )
        authorization = base64.b64encode(
            authorization_origin.encode("utf-8")
        ).decode("ascii")
        query = urlencode(
            {"host": host, "date": date, "authorization": authorization}
        )
        return urlunsplit((parsed.scheme, host, path, query, ""))

    def _build_request_body(self, *, text: str, domain: str) -> dict[str, object]:
        message_json = json.dumps(
            {"messages": [{"content": text, "role": "user"}]},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        # The protocol includes uid, but no demo/business identifier is ever
        # hard-coded. Deployments that require one supply it explicitly.
        header: dict[str, object] = {
            "app_id": self._app_id,
            "uid": self._uid or "",
            "status": 3,
        }
        return {
            "header": header,
            "parameter": {
                "emb": {
                    "domain": domain,
                    "feature": {"encoding": "utf8"},
                }
            },
            "payload": {
                "messages": {
                    "text": base64.b64encode(
                        message_json.encode("utf-8")
                    ).decode("ascii")
                }
            },
        }

    def _parse_response(self, response: httpx.Response) -> list[float]:
        try:
            data: Any = response.json()
            header = data["header"]
            code = int(header["code"])
        except (ValueError, TypeError, KeyError) as exc:
            raise EmbeddingResponseError(
                "Xfyun Embedding response is not valid JSON"
            ) from exc
        if code != 0:
            message = str(header.get("message") or header.get("msg") or "unknown error")
            sid = str(header.get("sid") or "")
            logger.warning(
                "Embedding response provider=xfyun_native code=%s sid=%s message=%s",
                code,
                sid,
                message,
            )
            raise EmbeddingResponseError(
                f"Xfyun Embedding returned code {code}: {message}"
            )
        try:
            encoded = data["payload"]["feature"]["text"]
            decoded = base64.b64decode(encoded, validate=True)
        except (KeyError, TypeError, ValueError, binascii.Error) as exc:
            raise EmbeddingResponseError(
                "Xfyun Embedding response contains invalid vector encoding"
            ) from exc
        try:
            import numpy as np
        except ImportError as exc:
            raise EmbeddingConfigurationError(
                "numpy is required for Xfyun native embeddings"
            ) from exc
        vector = np.frombuffer(decoded, dtype=np.dtype(np.float32).newbyteorder("<"))
        if len(vector) != self._dimension:
            raise EmbeddingResponseError(
                "Xfyun Embedding vector dimension mismatch: "
                f"expected {self._dimension}, received {len(vector)}"
            )
        if not np.isfinite(vector).all():
            raise EmbeddingResponseError(
                "Xfyun Embedding response contains non-finite vector values"
            )
        return vector.astype(float).tolist()

    def _validate_configuration(self) -> None:
        required = (
            ("XFYUN_EMBEDDING_APP_ID", self._app_id),
            ("XFYUN_EMBEDDING_API_KEY", self._api_key),
            ("XFYUN_EMBEDDING_API_SECRET", self._api_secret),
            ("XFYUN_EMBEDDING_URL", self._url),
        )
        for name, value in required:
            if not value or not value.strip():
                raise EmbeddingConfigurationError(f"{name} is required")
        parsed = urlsplit(self._url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise EmbeddingConfigurationError(
                "XFYUN_EMBEDDING_URL must be a valid HTTPS URL"
            )
        if self._dimension <= 0:
            raise EmbeddingConfigurationError(
                "XFYUN_EMBEDDING_DIMENSION must be greater than zero"
            )
        if self._max_concurrency <= 0:
            raise EmbeddingConfigurationError(
                "XFYUN_EMBEDDING_MAX_CONCURRENCY must be greater than zero"
            )
        if self._timeout_seconds <= 0:
            raise EmbeddingConfigurationError(
                "EMBEDDING_TIMEOUT_SECONDS must be greater than zero"
            )

    @staticmethod
    def _validate_texts(texts: list[str]) -> None:
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise EmbeddingError("Embedding input text must be non-empty")

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
        if provider_name in {"xfyun_native", "xfyun"}:
            # ``xfyun`` is retained only as a legacy alias for the native
            # Xfyun HTTP/HMAC protocol; it is not OpenAI-compatible.
            return XfyunNativeEmbeddingProvider()
        if provider_name in {"openai_compatible", "siliconflow"}:
            return OpenAICompatibleEmbeddingProvider()
        raise EmbeddingConfigurationError(
            f"Unsupported EMBEDDING_PROVIDER: {settings.embedding_provider}. "
            "Inject an EmbeddingProvider implementation for local/BGE models."
        )
