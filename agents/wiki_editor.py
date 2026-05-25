"""
wiki_editor.py — 知识主编 (比对与决策)
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Any, Optional, Literal
from agno.agent import Agent
from core.llm_factory import get_qwen_model


# 💡 我们把 Action 的定义移交给了主编，因为只有它才有权下达动作指令
class Action(BaseModel):
    type: Literal["create", "edit", "append_link"] = Field(description="必须严格使用这三个词之一")
    file: str = Field(description="文件路径")
    title: Optional[str] = Field(default=None)
    tags: Optional[List[str]] = Field(default=None)
    abstract: Optional[str] = Field(default=None)
    old_str: Optional[str] = Field(default=None)
    content: Optional[str] = Field(default=None)
    link_to: Optional[str] = Field(default=None)
    rationale: str = Field(description="操作理由")

    @field_validator('tags', mode='before')
    @classmethod
    def ensure_list(cls, v: Any):
        if isinstance(v, str):
            return [tag.strip() for tag in v.split(',') if tag.strip()]
        return v


class EditorReport(BaseModel):
    actions: List[Action] = Field(description="精准的比对修改动作列表")


class WikiEditor:
    def __init__(self):
        # 💡 主编的核心 SOP：严禁盲猜，必须基于旧文件内容进行精准修改
        self.instructions = """你是一个严谨的本地知识库主编。
        你的核心任务是：根据【新摄入资料】和【本地已有文件内容】，进行知识融合比对，并输出精确的文件修改动作(actions)。

        ⚠️ 核心执行协议：
        1. 【查重与去重】：如果新资料的内容在【本地已有文件】中已经存在，或者没有实质性的新信息，请直接忽略，不要生成任何动作！
        2. 【全新创建】：如果这是一个全新的概念（本地没有它的文件），生成 'create' 动作。正文需包含详实的深度笔记，并大量使用 [[双链]]。随后，必须附带一个 'append_link' 动作，将其分类追加到 index.md。
        3. 【精准融合 (edit)】：如果本地已经存在该概念的文件，且新资料提供了增量细节（如新公式、新应用场景）：
           - 必须生成 'edit' 动作。
           - `old_str`：必须从【本地已有文件内容】中一字不差地复制需要被替换/扩展的原有段落！
           - `content`：写入融合了新旧知识的全新段落。
        4. 【强制双链】：所有技术术语、模型名称必须用 [[ ]] 包裹。
        5.【专注原则】：在当前的决策中，你只被允许修改你在【本地已有文件内容】中亲眼看到的文件（如 index.md 和当前的目标概念文件）。绝对、绝对不允许尝试去 edit 任何未在此上下文中展示的旧文件！
        6.
        """
        self.agent = Agent(
            model=get_qwen_model(),
            instructions=[self.instructions],
            output_schema=EditorReport,
            stream=False
        )

    def merge(self, raw_text: str, analyst_summary: str, existing_context: str) -> dict:
        print("\n[WikiEditor] 🧠 主编正在比对新旧知识，生成精准融合指令...")

        user_prompt = f"""
        【新资料摘要】:
        {analyst_summary}

        【新摄入的完整资料】:
        {raw_text}

        ---
        【本地已有文件内容】(供查重、对比和提取 old_str 参考):
        {existing_context}

        请严格按 JSON 格式输出 actions。如果找不到原文字符串，绝对不要编造 old_str！
        """
        response = self.agent.run(user_prompt)

        if isinstance(response.content, str):
            raise ValueError("大模型未返回合法的 Pydantic 对象。")

        return response.content.model_dump()