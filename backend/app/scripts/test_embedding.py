"""Safely smoke-test the configured embedding provider.

Run from ``backend`` with: ``python -m app.scripts.test_embedding``.
"""

from __future__ import annotations

import asyncio
from time import perf_counter

from app.core.config import settings
from app.services.embedding_service import EmbeddingService


async def main() -> None:
    started = perf_counter()
    service = EmbeddingService()
    document_vectors = await service.embed_documents(
        [
            "生成式人工智能可以支持学习者进行反思。",
            "本研究面向六年级学生。",
        ]
    )
    query_vector = await service.embed_query("AI如何支持学生反思？")
    document_dimension = len(document_vectors[0]) if document_vectors else 0
    print(f"provider: {settings.embedding_provider}")
    print(f"documents: {len(document_vectors)}")
    print(f"document dimension: {document_dimension}")
    print(f"query dimension: {len(query_vector)}")
    print(f"duration_ms: {round((perf_counter() - started) * 1000)}")


if __name__ == "__main__":
    asyncio.run(main())
