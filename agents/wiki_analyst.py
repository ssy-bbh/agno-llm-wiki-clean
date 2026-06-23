from pydantic import BaseModel, Field
from typing import List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from agno.agent import Agent
from core.llm_factory import get_qwen_model

# 单次 LLM 调用超时（秒）
LLM_TIMEOUT_SECONDS = 90


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

                ⚠️ 极其严格的提取规则：
                1. 【实体标准】：只提取真正的技术实体、算法模型名称或核心机制。
                2. 【严禁项】：绝对禁止提取论文标题、作者、会议名、或过于泛指的大词。
                3. 【宁缺毋滥】：每个知识块最多提取 1 到 4 个最核心的概念！若无核心实体，返回空列表 []。
                4. 【名称洗牌】：使用学术界公认的简短缩写（如把 "Region Proposal Networks" 统一为 "RPN"）。
                5. 🌐【强制双语格式】：所有核心概念必须强制使用 `英文原名 (中文翻译)` 的标准格式输出！即使原文全是英文或全是中文，你也必须补齐另一种语言。
                   ✅ 正确示范：`Self-Attention (自注意力机制)`, `YOLO (单阶段目标检测算法)`, `CNN (卷积神经网络)`
                   ❌ 错误示范：`Self-Attention`, `自注意力机制`, `Self-Attention（自注意力机制）等`
                """
        # 📉 分层模型：MAP 提取是简单任务，用轻量模型省 90% 费用
        self.agent = Agent(
            model=get_qwen_model(model_id="qwen-turbo"),
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
        # 超时保护：防止 LLM 卡住导致整个流水线停滞
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.agent.run, user_prompt)
            try:
                response = future.result(timeout=LLM_TIMEOUT_SECONDS)
            except FuturesTimeoutError:
                print(f"\n⏰ [WikiAnalyst] LLM 调用超时 ({LLM_TIMEOUT_SECONDS}s)，跳过此块")
                return {"new_concepts": [], "summary": "(LLM 超时，未提取)"}

        if isinstance(response.content, str):
            print("\n🚨 Pydantic 解析失败！原始字符串是：\n", response.content)
            raise ValueError("大模型未返回合法的 Pydantic 对象。")

        return response.content.model_dump()