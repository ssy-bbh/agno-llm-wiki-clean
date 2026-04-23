"""
wiki_analyst.py — 纯手写、绝对可控的知识分析师
"""
import json
from agno.agent import Agent
from prompts.wiki_prompt import build_analyst_system_prompt
# 引入你写好的 core/llm_factory
from core.llm_factory import get_qwen_model


class WikiAnalyst:
    def __init__(self):
        self.instructions = build_analyst_system_prompt()
        # 注意这里：用你写好的 get_qwen_model()，并且正确使用 instructions 参数
        self.agent = Agent(
            model=get_qwen_model(),
            instructions=[self.instructions],
            stream=False  # 先关掉流式，确保拿到的全是 JSON
        )

    def analyze(self, raw_text: str) -> dict:
        print("\n[WikiAnalyst] 正在分析文本...")

        user_prompt = f"请分析以下内容并输出 JSON：\n{raw_text}"
        response = self.agent.run(user_prompt)
        text = response.content.strip()

        # 暴力清洗大模型可能带的 ```json 废话
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        return json.loads(text.strip())