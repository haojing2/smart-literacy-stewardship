from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import json
import logging
from urllib.parse import parse_qs, urlsplit

import httpx
import numpy as np
import pytest

from app.services.embedding_service import (
    EmbeddingService,
    EmbeddingConfigurationError,
    EmbeddingInputTooLargeError,
    EmbeddingResponseError,
    XfyunNativeEmbeddingProvider,
)
from app.core.config import settings


def response_payload(values: list[float], *, code: int = 0) -> dict[str, object]:
    encoded = base64.b64encode(
        np.asarray(values, dtype=np.dtype(np.float32).newbyteorder("<")).tobytes()
    ).decode("ascii")
    return {
        "header": {"code": code, "message": "test response", "sid": "sid-test"},
        "payload": {"feature": {"text": encoded}},
    }


def provider_with_transport(
    handler,
    *,
    dimension: int = 4,
    max_concurrency: int = 2,
) -> tuple[XfyunNativeEmbeddingProvider, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = XfyunNativeEmbeddingProvider(
        app_id="test-app",
        api_key="test-key",
        api_secret="test-secret",
        url="https://emb-cn-huabei-1.xf-yun.com/",
        dimension=dimension,
        max_concurrency=max_concurrency,
        timeout_seconds=1,
        uid="",
        client=client,
    )
    return provider, client


def test_native_requests_use_para_for_documents_and_query_for_query() -> None:
    domains: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.headers["content-type"] == "application/json"
        domains.append(body["parameter"]["emb"]["domain"])
        assert body["header"] == {"app_id": "test-app", "uid": "", "status": 3}
        message_payload = json.loads(
            base64.b64decode(body["payload"]["messages"]["text"])
        )
        assert message_payload == {
            "messages": [{"content": "document" if not domains[:-1] else "question", "role": "user"}]
        }
        return httpx.Response(200, json=response_payload([1, 2, 3, 4]))

    provider, client = provider_with_transport(handler)

    async def run() -> None:
        await provider.embed_documents(["document"])
        await provider.embed_query("question")
        await client.aclose()

    asyncio.run(run())
    assert domains == ["para", "query"]


def test_hmac_url_contains_host_date_authorization_and_root_request_path() -> None:
    provider, client = provider_with_transport(
        lambda request: httpx.Response(200, json=response_payload([1, 2, 3, 4]))
    )
    authenticated = provider._authenticated_url(
        now=datetime(2026, 9, 8, tzinfo=timezone.utc)
    )
    parsed = urlsplit(authenticated)
    query = parse_qs(parsed.query)

    assert parsed.path == "/"
    assert set(query) == {"host", "date", "authorization"}
    assert query["host"] == ["emb-cn-huabei-1.xf-yun.com"]
    authorization = base64.b64decode(query["authorization"][0]).decode("utf-8")
    assert 'api_key="test-key"' in authorization
    assert 'headers="host date request-line"' in authorization
    assert 'algorithm="hmac-sha256"' in authorization
    asyncio.run(client.aclose())


def test_success_decodes_little_endian_vector_and_validates_dimension() -> None:
    provider, client = provider_with_transport(
        lambda request: httpx.Response(200, json=response_payload([1.5, 2.5, 3.5, 4.5]))
    )
    vector = asyncio.run(provider.embed_query("question"))
    asyncio.run(client.aclose())
    assert vector == [1.5, 2.5, 3.5, 4.5]


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"header": {"code": 1001, "message": "bad request", "sid": "s"}}, "code 1001"),
        ({"header": {"code": 0}, "payload": {"feature": {"text": "not-base64"}}}, "invalid vector encoding"),
        (response_payload([1, 2, 3]), "dimension mismatch"),
        (response_payload([1, float("nan"), 3, 4]), "non-finite"),
    ],
)
def test_invalid_responses_raise_clear_errors(payload: dict[str, object], message: str) -> None:
    provider, client = provider_with_transport(
        lambda request: httpx.Response(200, json=payload)
    )
    with pytest.raises(EmbeddingResponseError, match=message):
        asyncio.run(provider.embed_query("question"))
    asyncio.run(client.aclose())


def test_document_result_order_and_concurrency_limit_are_preserved() -> None:
    active = 0
    maximum_active = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal active, maximum_active
        body = json.loads(request.content)
        encoded = body["payload"]["messages"]["text"]
        message = json.loads(base64.b64decode(encoded))["messages"][0]["content"]
        active += 1
        maximum_active = max(maximum_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        value = float(message.removeprefix("text-"))
        return httpx.Response(200, json=response_payload([value] * 4))

    provider, client = provider_with_transport(handler, max_concurrency=2)

    async def run() -> list[list[float]]:
        result = await provider.embed_documents([f"text-{index}" for index in range(6)])
        await client.aclose()
        return result

    vectors = asyncio.run(run())
    assert [vector[0] for vector in vectors] == [0, 1, 2, 3, 4, 5]
    assert maximum_active == 2


def test_configuration_is_validated_only_when_provider_is_used() -> None:
    provider = XfyunNativeEmbeddingProvider(
        app_id="",
        api_key="",
        api_secret="",
        url="https://emb-cn-huabei-1.xf-yun.com/",
    )
    with pytest.raises(
        EmbeddingConfigurationError,
        match="XFYUN_EMBEDDING_APP_ID is required",
    ):
        asyncio.run(provider.embed_query("question"))


def test_logs_never_contain_embedding_credentials(caplog: pytest.LogCaptureFixture) -> None:
    provider, client = provider_with_transport(
        lambda request: httpx.Response(
            200,
            json={"header": {"code": 1001, "message": "denied", "sid": "safe"}},
        )
    )
    caplog.set_level(logging.INFO)
    with pytest.raises(EmbeddingResponseError):
        asyncio.run(provider.embed_query("question"))
    asyncio.run(client.aclose())
    assert "test-key" not in caplog.text
    assert "test-secret" not in caplog.text


def test_transient_http_status_is_retried_with_a_finite_limit() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={})
        return httpx.Response(200, json=response_payload([1, 2, 3, 4]))

    provider, client = provider_with_transport(handler)
    provider._RETRY_DELAYS_SECONDS = (0, 0, 0)
    assert asyncio.run(provider.embed_query("question")) == [1, 2, 3, 4]
    asyncio.run(client.aclose())
    assert attempts == 2


@pytest.mark.parametrize("status", [429, 500])
def test_retryable_http_statuses_are_retried(status: int) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(status, json={"header": {"message": "retry"}})
        return httpx.Response(200, json=response_payload([1, 2, 3, 4]))

    provider, client = provider_with_transport(handler)
    provider._RETRY_DELAYS_SECONDS = (0,)
    assert asyncio.run(provider.embed_query("question")) == [1, 2, 3, 4]
    asyncio.run(client.aclose())
    assert attempts == 2


def test_http_401_is_safe_and_not_retried() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            401,
            json={"header": {"code": 10005, "message": "auth denied", "sid": "safe-sid"}},
        )

    provider, client = provider_with_transport(handler)
    with pytest.raises(EmbeddingResponseError) as caught:
        asyncio.run(provider.embed_query("question"))
    asyncio.run(client.aclose())
    message = str(caught.value)
    assert attempts == 1
    assert "http_status=401" in message
    assert "xfyun_code=10005" in message
    assert "auth denied" in message and "safe-sid" in message
    assert "test-key" not in message and "test-secret" not in message
    assert "authorization" not in message


def test_oversize_payload_fails_before_http_request() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json=response_payload([1, 2, 3, 4]))

    provider, client = provider_with_transport(handler)
    provider._max_payload_bytes = 20
    with pytest.raises(EmbeddingInputTooLargeError, match="encoded_payload_bytes"):
        asyncio.run(provider.embed_query("question"))
    asyncio.run(client.aclose())
    assert attempts == 0


def test_first_document_is_a_probe_before_parallel_requests() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        encoded = body["payload"]["messages"]["text"]
        text = json.loads(base64.b64decode(encoded))["messages"][0]["content"]
        requested.append(text)
        return httpx.Response(
            401, json={"header": {"code": 1, "message": "denied", "sid": "s"}}
        )

    provider, client = provider_with_transport(handler)
    with pytest.raises(EmbeddingResponseError):
        asyncio.run(provider.embed_documents(["first", "second", "third"]))
    asyncio.run(client.aclose())
    assert requested == ["first"]


def test_factory_maps_xfyun_and_native_alias_to_native_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "aliyun_embedding_provider", None)
    for provider_name in ("xfyun_native", "xfyun"):
        monkeypatch.setattr(settings, "embedding_provider", provider_name)
        assert isinstance(
            EmbeddingService._build_provider(),
            XfyunNativeEmbeddingProvider,
        )
