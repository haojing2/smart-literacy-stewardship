"""Manual Spark Assistant smoke test; credentials must come from the environment."""

import os

from sparkai.core.messages import ChatMessage
from sparkai.llm.llm import ChatSparkLLM


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be set before running this manual demo")
    return value

if __name__ == '__main__':
    spark = ChatSparkLLM(
        spark_api_url=_required("RESEARCH_AGENT_URL"),
        spark_app_id=_required("SPARK_ASSISTANT_APP_ID"),
        spark_api_key=_required("SPARK_ASSISTANT_API_KEY"),
        spark_api_secret=_required("SPARK_ASSISTANT_API_SECRET"),
        spark_llm_domain=os.getenv("RESEARCH_AGENT_DOMAIN", "generalv3.5"),
        streaming=False,
    )
    messages = [ChatMessage(
        role="user",
        content='你好呀,你是谁'
    )]
    print(spark.generate([messages]))
