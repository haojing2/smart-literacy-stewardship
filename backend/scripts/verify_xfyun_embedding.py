"""Safely verify the configured native Xfyun Embedding endpoint."""

from __future__ import annotations

import asyncio
import math
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.services.embedding_service import EmbeddingResponseError, EmbeddingService


def _configured(value: str | None) -> str:
    return "yes" if value and value.strip() else "no"


def _masked_app_id(value: str | None) -> str:
    cleaned = (value or "").strip()
    return f"****{cleaned[-3:]}" if cleaned else "not configured"


async def _run() -> None:
    print(f"provider={settings.embedding_provider}")
    print(f"endpoint={settings.xfyun_embedding_url}")
    print(f"APPID configured={_configured(settings.xfyun_embedding_app_id)} ({_masked_app_id(settings.xfyun_embedding_app_id)})")
    print(f"APIKey configured={_configured(settings.xfyun_embedding_api_key)}")
    print(f"APISecret configured={_configured(settings.xfyun_embedding_api_secret)}")
    print(f"UID configured={_configured(settings.xfyun_embedding_uid)}")
    print(f"dimension={settings.xfyun_embedding_dimension}")

    service = EmbeddingService()
    documents = await service.embed_documents(["测试知识库向量化"])
    query = await service.embed_query("什么是知识库向量化？")
    expected = settings.xfyun_embedding_dimension
    if len(documents) != 1 or len(documents[0]) != expected or not all(map(math.isfinite, documents[0])):
        raise RuntimeError("para embedding returned an invalid vector")
    if len(query) != expected or not all(map(math.isfinite, query)):
        raise RuntimeError("query embedding returned an invalid vector")
    print(f"para embedding: OK, dimension={len(documents[0])}")
    print(f"query embedding: OK, dimension={len(query)}")


if __name__ == "__main__":
    try:
        asyncio.run(_run())
    except EmbeddingResponseError as exc:
        print(str(exc))
        if "http_status=401" in str(exc):
            print("- 检查 APPID/APIKey/APISecret 是否属于同一个讯飞应用")
            print("- 检查该 APPID 是否已经开通 llm embedding 服务")
            print("- 检查系统时间是否正确")
            print("- 检查 backend/.env 是否为实际加载的配置文件")
        raise SystemExit(1) from None
