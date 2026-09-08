from __future__ import annotations

import asyncio
import os

from demo_common import BACKEND_ROOT
from app.assistants.spark_client import SparkLLMClient
from app.core.config import ENV_FILE, settings


def print_diagnostics() -> None:
    print(f"sys.executable: {os.sys.executable}")
    print(f"current working directory: {os.getcwd()}")
    print(f"backend root: {BACKEND_ROOT}")
    print(f"env file exists: {ENV_FILE.is_file()}")
    print(f"llm_provider: {settings.llm_provider}")
    print(f"spark_api_base: {settings.spark_api_base}")
    print(f"spark_model_id: {settings.spark_model_id}")
    print(f"spark_api_key configured: {bool(settings.spark_api_key)}")


async def main() -> None:
    print_diagnostics()
    print(await SparkLLMClient().chat([{"role": "user", "content": "你好"}]))


if __name__ == "__main__":
    asyncio.run(main())
