from pydantic import BaseModel, Field
from typing import List
from agno.agent import Agent
from core.llm_factory import get_qwen_model


# 💡 变化 1：把 Action 类彻底删除了！它不配拥有这个权力。
# 💡 变化 2：AnalysisReport 里去掉了 actions，加上了一个 summary 备用。
class AnalysisReport(BaseModel):
    new_concepts: List[str] = Field(description="从新资料中提取出的核心概念列表（如算法、模型、架构、术语等）")
    summary: str = Field(description="新资料的核心内容摘要（约50-100字），用于后续提供上下文")


class WikiAnalyst:
    def __init__(self):
        # 💡 变化 3：Prompt 彻底大换血，告诉它：你只是个看材料的，别管怎么存！
        self.instructions = """你是一个专业的知识图谱情报侦察兵。

        你的【唯一任务】是阅读新摄入的资料，提取其中的核心技术概念，并写一段简短的内容摘要。
        你绝对不要关心这些知识如何写入文件，也绝对不要生成任何操作动作。

        输出要求：
        1. new_concepts: 提取出资料中出现的所有重要技术概念、算法、模型、专有名词。
        2. summary: 用一两句话精准概括这段资料的核心信息。
        """
        self.agent = Agent(
            model=get_qwen_model(),
            instructions=[self.instructions],
            output_schema=AnalysisReport,
            stream=False
        )

    def analyze(self, raw_text: str) -> dict:
        # 💡 变化 4：它不需要再读取本地 index.md 了，减轻它的认知负担。
        print("\n[WikiAnalyst] 🕵️‍♂️ 侦察兵正在阅读新资料并提取概念...")

        user_prompt = f"""
        【新摄入的资料】:
        {raw_text}

        请提取核心概念并生成摘要。
        """
        response = self.agent.run(user_prompt)

        if isinstance(response.content, str):
            print("\n🚨 Pydantic 解析失败！原始字符串是：\n", response.content)
            raise ValueError("大模型未返回合法的 Pydantic 对象。")

        return response.content.model_dump()