from openai import OpenAI
import os


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} must be set before running this manual demo")
    return value

client = OpenAI(
    api_key=_required("SPARK_API_KEY"),
    base_url=os.getenv("SPARK_API_BASE", "https://maas-api.cn-huabei-1.xf-yun.com/v2"),
)

def unified_chat_test(model_id, messages, use_stream=False, extra_body={}):
    """
    一个统一的函数，用于演示多种调用场景。

    :param model_id: 要调用的模型ID。
    :param messages: 对话消息列表。
    :param use_stream: 是否使用流式输出。
    :param extra_body: 包含额外请求参数的字典，如 response_format。
    """
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=messages,
            stream=use_stream,
            temperature=0.7,
            max_tokens=4096,
            extra_headers={"lora_id": "0"},  # 调用微调大模型时,对应替换为模型服务卡片上的resourceId
            stream_options={"include_usage": True},
            extra_body=extra_body
        )

        if use_stream:
            # 处理流式响应
            full_response = ""
            print("--- 流式输出 ---")
            for chunk in response:
                if not chunk.choices:
                    continue
                if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    print(content, end="", flush=True)
                    full_response += content
            print("\n\n--- 完整响应 ---")
            print(full_response)
        else:
            # 处理非流式响应
            print("--- 非流式输出 ---")
            message = response.choices[0].message
            print(message.content)

    except Exception as e:
        print(f"请求出错: {e}")

if __name__ == "__main__":
    model_id = "spark-x2.5-1.7b" # 必填：调用大模型时，对应为推理服务的模型卡片上对应的modelId

    # 普通流式调用
    print("********* 普通流式调用 *********")
    stream_messages = [{"role": "user", "content": "hello"}]
    unified_chat_test(model_id, stream_messages, use_stream=True)
