"""Manually verify Spark's configured non-streaming and streaming modes."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.assistants.spark_client import SparkLLMClient, SparkLLMError  # noqa: E402
from app.core.config import settings  # noqa: E402


async def main() -> int:
    started = time.perf_counter()
    try:
        client = SparkLLMClient()
        response = await client.chat([{"role": "user", "content": "你好"}])
        if not response:
            raise SparkLLMError("non-stream response was empty")

        parts: list[str] = []
        async for content in client.stream_chat([{"role": "user", "content": "你好"}]):
            parts.append(content)
        full_response = "".join(parts).strip()
        if not full_response:
            raise SparkLLMError("stream response was empty")
    except SparkLLMError as exc:
        print("Spark connection: FAILED")
        print(f"exception_type: {type(exc).__name__}")
        print(f"error: {exc}")
        return 1
    except Exception as exc:
        print("Spark connection: FAILED")
        print(f"exception_type: {type(exc).__name__}")
        print("error: unexpected client failure (details intentionally suppressed)")
        return 1

    elapsed_ms = (time.perf_counter() - started) * 1000
    print("Spark connection: OK")
    print("provider: spark")
    print(f"model_id: {settings.spark_model_id}")
    print(f"non_stream_response: {response}")
    print(f"stream_response: {full_response}")
    print(f"elapsed_ms: {elapsed_ms:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
