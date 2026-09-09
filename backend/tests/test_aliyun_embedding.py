from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.core.config import Settings, settings
from app.services.chunk_service import ChunkService
from app.services.embedding_service import (
    EmbeddingResponseError,
    EmbeddingService,
    OpenAICompatibleEmbeddingProvider,
)
from app.services.knowledge_base_path_service import KnowledgeBasePathService
from app.services.vector_store_service import VectorStoreService


class FakeEmbeddings:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def _response(vectors: list[list[float]]) -> object:
    return SimpleNamespace(
        data=[
            SimpleNamespace(index=index, embedding=vector)
            for index, vector in reversed(list(enumerate(vectors)))
        ]
    )


def _provider(vectors: list[list[float]]) -> tuple[OpenAICompatibleEmbeddingProvider, FakeEmbeddings]:
    embeddings = FakeEmbeddings(_response(vectors))
    provider = OpenAICompatibleEmbeddingProvider(
        api_key="fake-key",
        base_url="https://example.invalid/compatible-mode/v1",
        model="qwen3.7-text-embedding-flash",
        dimension=1024,
        encoding_format="float",
        timeout_seconds=60,
    )
    provider._client = lambda: SimpleNamespace(embeddings=embeddings)  # type: ignore[method-assign]
    return provider, embeddings


def test_mixed_case_aliyun_env_fields_are_loaded(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "MYSQL_HOST=localhost",
                "MYSQL_USER=test",
                "MYSQL_PASSWORD=test",
                "MYSQL_DATABASE=test",
                "JWT_SECRET_KEY=test",
                "Aliyun_EMBEDDING_PROVIDER=openai_compatible",
                "Aliyun_EMBEDDING_API_KEY=fake-key",
                "Aliyun_EMBEDDING_URL=https://example.invalid/compatible-mode/v1",
                "Aliyun_EMBEDDING_MODEL=qwen3.7-text-embedding-flash",
                "Aliyun_EMBEDDING_DIMENSION=1024",
                "Aliyun_EMBEDDING_BATCH_SIZE=25",
                "Aliyun_EMBEDDING_TIMEOUT_SECONDS=60",
            ]
        ),
        encoding="utf-8",
    )
    loaded = Settings(_env_file=env_file)
    assert loaded.aliyun_embedding_provider == "openai_compatible"
    assert loaded.aliyun_embedding_api_key == "fake-key"
    assert loaded.aliyun_embedding_url.endswith("/compatible-mode/v1")
    assert loaded.aliyun_embedding_model == "qwen3.7-text-embedding-flash"
    assert loaded.aliyun_embedding_dimension == 1024
    assert loaded.aliyun_embedding_batch_size == 25
    assert loaded.aliyun_embedding_timeout_seconds == 60.0


def test_documents_and_query_send_qwen_dimensions_and_float_encoding() -> None:
    provider, embeddings = _provider([[float(index) for index in range(1024)]])
    assert len(asyncio.run(provider.embed_documents(["document"]))[0]) == 1024
    assert len(asyncio.run(provider.embed_query("query"))) == 1024
    assert embeddings.calls == [
        {
            "model": "qwen3.7-text-embedding-flash",
            "input": ["document"],
            "encoding_format": "float",
            "dimensions": 1024,
        },
        {
            "model": "qwen3.7-text-embedding-flash",
            "input": ["query"],
            "encoding_format": "float",
            "dimensions": 1024,
        },
    ]


def test_response_order_dimension_and_finite_values_are_validated() -> None:
    first = [1.0] * 1024
    second = [2.0] * 1024
    provider, _ = _provider([first, second])
    result = asyncio.run(provider.embed_documents(["first", "second"]))
    assert result[0][0] == 1.0 and result[1][0] == 2.0

    wrong_dimension, _ = _provider([[1.0] * 768])
    with pytest.raises(EmbeddingResponseError, match="expected 1024, received 768"):
        asyncio.run(wrong_dimension.embed_query("query"))

    non_finite, _ = _provider([[float("nan")] + [1.0] * 1023])
    with pytest.raises(EmbeddingResponseError, match="invalid vector"):
        asyncio.run(non_finite.embed_query("query"))


def test_aliyun_documents_are_batched_at_25_and_keep_order() -> None:
    class BatchEmbeddings:
        def __init__(self) -> None:
            self.batch_lengths: list[int] = []

        async def create(self, **kwargs):
            inputs = kwargs["input"]
            self.batch_lengths.append(len(inputs))
            return _response([[float(text.removeprefix("text-"))] * 1024 for text in inputs])

    embeddings = BatchEmbeddings()
    provider = OpenAICompatibleEmbeddingProvider(
        api_key="fake-key",
        model="qwen3.7-text-embedding-flash",
        dimension=1024,
        encoding_format="float",
        batch_size=25,
    )
    provider._client = lambda: SimpleNamespace(embeddings=embeddings)  # type: ignore[method-assign]
    vectors = asyncio.run(
        provider.embed_documents([f"text-{index}" for index in range(30)])
    )
    assert embeddings.batch_lengths == [25, 5]
    assert [vector[0] for vector in vectors] == list(map(float, range(30)))


def test_aliyun_factory_has_priority_and_is_not_subject_to_xfyun_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "aliyun_embedding_provider", "aliyun")
    monkeypatch.setattr(settings, "aliyun_embedding_api_key", "fake-key")
    monkeypatch.setattr(settings, "aliyun_embedding_url", "https://example.invalid/v1")
    monkeypatch.setattr(settings, "aliyun_embedding_dimension", 1024)
    monkeypatch.setattr(settings, "xfyun_embedding_max_payload_bytes", 1)
    provider = EmbeddingService._build_provider()
    assert isinstance(provider, OpenAICompatibleEmbeddingProvider)
    provider._client = lambda: SimpleNamespace(  # type: ignore[method-assign]
        embeddings=FakeEmbeddings(_response([[1.0] * 1024]))
    )
    long_text = "中文论文内容" * 1000
    assert len(asyncio.run(provider.embed_query(long_text))) == 1024


def test_chunk_service_remains_generic_and_faiss_accepts_1024_dimensions(tmp_path) -> None:
    class Splitter:
        def split_text(self, text: str) -> list[str]:
            return [text]

    text = "中文论文内容" * 1000
    chunks = ChunkService(splitter=Splitter()).chunk_markdown(
        markdown=text, project_id=1, file_id=1, filename="paper.md"
    )
    assert chunks[0].content == text
    store = VectorStoreService(KnowledgeBasePathService(tmp_path))
    index = store.create_or_update_index(
        project_id=1, chunks=chunks, embeddings=[[1.0] * 1024]
    )
    assert index.index.d == 1024
    assert index.search([1.0] * 1024, top_k=1)[0].chunk.chunk_id == chunks[0].chunk_id
