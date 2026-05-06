# core/llm_factory.py
import os
from dotenv import load_dotenv
from agno.models.openai.like import OpenAILike

# 确保加载环境变量
load_dotenv()


def get_qwen_model(model_id="deepseek-v4-pro"):
    api_key = os.getenv("QWEN_API_KEY")
    if not api_key:
        raise ValueError("⚠️ 未找到 QWEN_API_KEY，请检查 .env 文件！")

    return OpenAILike(
        id=model_id,
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        # 核心抗篡改护城河
        role_map={"system": "system", "user": "user", "assistant": "assistant", "tool": "tool"}
    )