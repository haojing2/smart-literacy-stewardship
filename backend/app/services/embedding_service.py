"""Vendor-neutral embedding facade for future local knowledge-base retrieval."""

from __future__ import annotations

import asyncio
import base64
import binascii
from datetime import datetime
import hashlib
import hmac
import json
import logging
import math
from time import mktime, perf_counter
from typing import Any, Protocol
from urllib.parse import urlencode, urlsplit, urlunsplit
from wsgiref.handlers import format_date_time

import httpx

from app.core.config import settings


logger = logging.getLogger(__name__)


def build_xfyun_message_json(text: str) -> str:
    """Serialize the exact inner message sent to Xfyun."""
    message = {"messages": [{"content": text, "role": "user"}]}
    return json.dumps(message, ensure_ascii=False, separators=(",", ":"))


def build_xfyun_payload_text(text: str) -> str:
    """Return the Base64 value used as ``payload.messages.text``."""
    return base64.b64encode(build_xfyun_message_json(text).encode("utf-8")).decode(
        "ascii"
    )


def get_xfyun_payload_size_bytes(text: str) -> int:
    """Measure the actual UTF-8 byte size of the final Base64 field."""
    return len(build_xfyun_payload_text(text).encode("utf-8"))


class EmbeddingError(RuntimeError):
    pass


class EmbeddingConfigurationError(EmbeddingError):
    pass


class EmbeddingResponseError(EmbeddingError):
    pass


class EmbeddingInputTooLargeError(EmbeddingError):
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
        dimension: int | None = None,
        encoding_format: str = "float",
        batch_size: int | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.embedding_api_key
        self._base_url = base_url if base_url is not None else settings.embedding_base_url
        self._model = model if model is not None else settings.embedding_model
        self._dimension = dimension
        self._encoding_format = encoding_format
        self._batch_size = batch_size
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
        batch_size = self._batch_size or len(texts)
        client = self._client()
        started = perf_counter()
        try:
            vectors: list[list[float]] = []
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                kwargs: dict[str, object] = {
                    "model": self._model,
                    "input": batch,
                    "encoding_format": self._encoding_format,
                }
                if self._dimension is not None:
                    kwargs["dimensions"] = self._dimension
                response = await client.embeddings.create(**kwargs)
                batch_vectors = self._extract_vectors(response)
                if len(batch_vectors) != len(batch):
                    raise EmbeddingResponseError(
                        "Embedding response count does not match input count"
                    )
                vectors.extend(batch_vectors)
        except EmbeddingError:
            raise
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            detail = f" http_status={status}" if status is not None else ""
            raise EmbeddingResponseError(
                f"OpenAI-compatible embedding request failed:{detail or ' provider error'}"
            ) from exc
        finally:
            close = getattr(client, "close", None)
            if close is not None:
                await close()
            logger.info(
                "Embedding request provider=openai_compatible model=%s duration_ms=%s",
                self._model,
                round((perf_counter() - started) * 1000),
            )
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
        if self._dimension is not None and self._dimension <= 0:
            raise EmbeddingConfigurationError(
                "Embedding dimension must be greater than zero"
            )
        if self._batch_size is not None and self._batch_size <= 0:
            raise EmbeddingConfigurationError(
                "Embedding batch size must be greater than zero"
            )
        if not self._encoding_format or not self._encoding_format.strip():
            raise EmbeddingConfigurationError("Embedding encoding format is required")

    @staticmethod
    def _validate_texts(texts: list[str]) -> None:
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise EmbeddingError("Embedding input text must be non-empty")

    def _extract_vectors(self, response: object) -> list[list[float]]:
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
        if self._dimension is not None:
            for vector in vectors:
                if len(vector) != self._dimension:
                    raise EmbeddingResponseError(
                        "Embedding vector dimension mismatch: "
                        f"expected {self._dimension}, received {len(vector)}"
                    )
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
        max_payload_bytes: int | None = None,
        uid: str | None = None,
        timeout_seconds: float | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._app_id = (
            (settings.xfyun_embedding_app_id if app_id is None else app_id) or ""
        ).strip()
        self._api_key = (
            (settings.xfyun_embedding_api_key if api_key is None else api_key) or ""
        ).strip()
        self._api_secret = (
            (
                settings.xfyun_embedding_api_secret
                if api_secret is None
                else api_secret
            )
            or ""
        ).strip()
        self._url = ((settings.xfyun_embedding_url if url is None else url) or "").strip()
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
        self._max_payload_bytes = (
            settings.xfyun_embedding_max_payload_bytes
            if max_payload_bytes is None
            else max_payload_bytes
        )
        self._uid = (
            (settings.xfyun_embedding_uid if uid is None else uid) or ""
        ).strip()
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
        async with self._client_context() as client:
            first = await self._embed_one(texts[0], domain="para", client=client)
            if len(texts) == 1:
                return [first]
            tasks = [
                asyncio.create_task(self._embed_one(text, domain="para", client=client))
                for text in texts[1:]
            ]
            try:
                remaining = await asyncio.gather(*tasks)
            except BaseException:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise
            return [first, *remaining]

    async def embed_query(self, query: str) -> list[float]:
        self._validate_configuration()
        self._validate_texts([query])
        async with self._client_context() as client:
            return await self._embed_one(query, domain="query", client=client)

    async def _embed_one(
        self, text: str, *, domain: str, client: httpx.AsyncClient
    ) -> list[float]:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrency)
        async with self._semaphore:
            started = perf_counter()
            try:
                response = await self._post_with_retry(
                    body=self._build_request_body(text=text, domain=domain),
                    domain=domain,
                    client=client,
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
        self, *, body: dict[str, object], domain: str, client: httpx.AsyncClient
    ) -> httpx.Response:
        for attempt in range(len(self._RETRY_DELAYS_SECONDS) + 1):
            try:
                response = await self._post(
                    url=self._build_xfyun_auth_url(self._url),
                    body=body,
                    client=client,
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
                raise self._http_response_error(response)
            return response
        raise EmbeddingResponseError("Xfyun Embedding request failed")

    async def _post(
        self, *, url: str, body: dict[str, object], client: httpx.AsyncClient
    ) -> httpx.Response:
        return await client.post(
            url, json=body, headers={"content-type": "application/json"}
        )

    def _build_xfyun_auth_url(
        self, request_url: str, method: str = "POST", *, now: datetime | None = None
    ) -> str:
        parsed = urlsplit(request_url)
        host = parsed.netloc
        path = parsed.path or "/"
        current = now or datetime.now()
        date = format_date_time(mktime(current.timetuple()))
        signature_origin = f"host: {host}\ndate: {date}\n{method} {path} HTTP/1.1"
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

    def _authenticated_url(self, *, now: datetime | None = None) -> str:
        return self._build_xfyun_auth_url(self._url, now=now)

    def _build_request_body(self, *, text: str, domain: str) -> dict[str, object]:
        if domain not in {"para", "query"}:
            raise EmbeddingError("Xfyun Embedding domain must be 'para' or 'query'")
        payload_text = build_xfyun_payload_text(text)
        payload_bytes = len(payload_text.encode("utf-8"))
        if payload_bytes > self._max_payload_bytes:
            raise EmbeddingInputTooLargeError(
                "Xfyun Embedding input is too large: "
                f"original_text_length={len(text)}, encoded_payload_bytes={payload_bytes}, "
                f"allowed_bytes={self._max_payload_bytes}"
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
                    "text": payload_text
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
        if self._max_payload_bytes <= 0:
            raise EmbeddingConfigurationError(
                "XFYUN_EMBEDDING_MAX_PAYLOAD_BYTES must be greater than zero"
            )
        if self._timeout_seconds <= 0:
            raise EmbeddingConfigurationError(
                "EMBEDDING_TIMEOUT_SECONDS must be greater than zero"
            )

    @staticmethod
    def _validate_texts(texts: list[str]) -> None:
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise EmbeddingError("Embedding input text must be non-empty")

    def _client_context(self):
        if self._client is not None:
            return _BorrowedAsyncClient(self._client)
        return httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=False,
        )

    @staticmethod
    def _http_response_error(response: httpx.Response) -> EmbeddingResponseError:
        xfyun_code: object = "unknown"
        message = "unknown error"
        sid: object = ""
        try:
            payload = response.json()
            header = payload.get("header", {}) if isinstance(payload, dict) else {}
            if isinstance(header, dict):
                xfyun_code = header.get("code", payload.get("code", "unknown"))
                message = str(
                    header.get("message")
                    or header.get("msg")
                    or payload.get("message")
                    or payload.get("msg")
                    or message
                )
                sid = header.get("sid", payload.get("sid", ""))
        except (ValueError, TypeError):
            message = response.text[:1000]
        return EmbeddingResponseError(
            "Xfyun Embedding request failed: "
            f"http_status={response.status_code}, xfyun_code={xfyun_code}, "
            f"message={message}, sid={sid}"
        )


class _BorrowedAsyncClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def __aenter__(self) -> httpx.AsyncClient:
        return self._client

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        return None

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
        aliyun_provider = (settings.aliyun_embedding_provider or "").strip().lower()
        if aliyun_provider in {
            "openai_compatible",
            "aliyun_openai_compatible",
            "aliyun",
        }:
            return OpenAICompatibleEmbeddingProvider(
                api_key=settings.aliyun_embedding_api_key,
                base_url=settings.aliyun_embedding_url,
                model=settings.aliyun_embedding_model,
                dimension=settings.aliyun_embedding_dimension,
                encoding_format="float",
                batch_size=settings.aliyun_embedding_batch_size,
                timeout_seconds=settings.aliyun_embedding_timeout_seconds,
            )
        if aliyun_provider:
            raise EmbeddingConfigurationError(
                f"Unsupported Aliyun embedding provider: {settings.aliyun_embedding_provider}"
            )
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
