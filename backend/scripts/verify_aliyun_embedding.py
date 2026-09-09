"""Safely verify the configured Aliyun OpenAI-compatible embedding service."""

from __future__ import annotations

import asyncio
import math
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.services.embedding_service import EmbeddingError, EmbeddingService


async def _run() -> None:
    print("provider=aliyun/openai_compatible")
    print(f"model={settings.aliyun_embedding_model}")
    print(f"dimension={settings.aliyun_embedding_dimension}")
    print(f"base_url configured={bool((settings.aliyun_embedding_url or '').strip())}")
    print(f"api_key configured={bool((settings.aliyun_embedding_api_key or '').strip())}")

    service = EmbeddingService()
    documents = await service.embed_documents(
        ["生成式人工智能可以支持学生反思性学习。"]
    )
    query = await service.embed_query("AI如何促进学生反思？")
    expected = settings.aliyun_embedding_dimension
    if (
        len(documents) != 1
        or len(documents[0]) != expected
        or not all(isinstance(value, float) and math.isfinite(value) for value in documents[0])
    ):
        raise RuntimeError("document embedding returned an invalid vector")
    if len(query) != expected or not all(
        isinstance(value, float) and math.isfinite(value) for value in query
    ):
        raise RuntimeError("query embedding returned an invalid vector")
    print(f"document embedding: OK, dimension={len(documents[0])}")
    print(f"query embedding: OK, dimension={len(query)}")


if __name__ == "__main__":
    try:
        asyncio.run(_run())
    except EmbeddingError as exc:
        print(str(exc))
        raise SystemExit(1) from None
