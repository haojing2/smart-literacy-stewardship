from __future__ import annotations

import asyncio

from demo_common import BACKEND_ROOT
from app.assistants.spark_client import SparkLLMClient


async def main() -> None:
    async for content in SparkLLMClient().stream_chat([{"role": "user", "content": "你好"}]):
        print(content, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(main())
