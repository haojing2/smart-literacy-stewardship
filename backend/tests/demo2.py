import os
from openai import OpenAI



def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be set before running this manual demo")
    return value


client = OpenAI(
    api_key=_required("SPARK_API_KEY"),
    base_url=os.getenv("SPARK_API_BASE", "https://spark-api-open.xf-yun.com/v2"),
)

# stream_res = True
stream_res = False

stream = client.chat.completions.create(
    messages=[
        {
            "role": "user",
            "content": "你好"
        },

    ],

    model="spark-x",
    stream=stream_res,
    user="123456",

)
full_response = ""

if not stream_res:
    print(stream.to_json())
else:
    for chunk in stream:
        if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[
            0].delta.reasoning_content is not None:
            reasoning_content = chunk.choices[0].delta.reasoning_content
            print(reasoning_content, end="", flush=True)  # 实时打印思考模型输出的思考过程每个片段

        if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content is not None:
            content = chunk.choices[0].delta.content
            print(content, end="", flush=True)  # 实时打印每个片段
            full_response += content

    print("\n\n ------完整响应：", full_response)
