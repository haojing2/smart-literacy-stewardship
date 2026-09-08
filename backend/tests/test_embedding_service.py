import asyncio

import pytest

from app.services.embedding_service import (
    EmbeddingError,
    EmbeddingService,
)


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.documents: list[str] | None = None
        self.query: str | None = None

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.documents = texts
        return [[float(index), 1.0] for index, _ in enumerate(texts)]

    async def embed_query(self, query: str) -> list[float]:
        self.query = query
        return [0.25, 0.75]


def test_embedding_service_has_vendor_neutral_document_and_query_methods() -> None:
    provider = FakeEmbeddingProvider()
    service = EmbeddingService(provider)

    assert asyncio.run(service.embed_documents(["first", "second"])) == [
        [0.0, 1.0],
        [1.0, 1.0],
    ]
    assert asyncio.run(service.embed_query("question")) == [0.25, 0.75]
    assert provider.documents == ["first", "second"]
    assert provider.query == "question"


def test_embedding_service_does_not_hide_provider_errors() -> None:
    class FailingProvider:
        async def embed_documents(self, texts: list[str]) -> list[list[float]]:
            raise EmbeddingError("provider unavailable")

        async def embed_query(self, query: str) -> list[float]:
            raise EmbeddingError("provider unavailable")

    with pytest.raises(EmbeddingError, match="provider unavailable"):
        asyncio.run(EmbeddingService(FailingProvider()).embed_query("question"))
