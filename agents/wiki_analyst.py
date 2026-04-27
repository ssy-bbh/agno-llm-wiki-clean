from pydantic import BaseModel, Field, field_validator
from typing import List, Any, Optional
from pathlib import Path
from agno.agent import Agent
from core.llm_factory import get_qwen_model

WIKI_ROOT = Path(__file__).parent.parent / "data" / "wiki"


class Action(BaseModel):
    type: str = Field(description="操作类型：'create', 'edit', 或 'append_link'")
    file: str = Field(description="文件路径")
    title: Optional[str] = Field(default=None)
    tags: Optional[List[str]] = Field(default=None)
    abstract: Optional[str] = Field(default=None)
    old_str: Optional[str] = Field(default=None)
    content: Optional[str] = Field(default=None)
    link_to: Optional[str] = Field(default=None)
    rationale: str = Field(description="操作理由")

    # 💡 拦截器：坚决防住大模型把 tags 列表写成字符串的偷懒行为
    @field_validator('tags', mode='before')
    @classmethod
    def ensure_list(cls, v: Any):
        if isinstance(v, str):
            return [tag.strip() for tag in v.split(',') if tag.strip()]
        return v


class AnalysisReport(BaseModel):
    new_concepts: List[str] = Field(description="提取出的概念")
    actions: List[Action] = Field(description="动作列表")


class WikiAnalyst:
    def __init__(self):
        # 💡 加强版紧箍咒：彻底封杀字符串拼接和多余前缀
        self.instructions = self.instructions = """你是一个专业的知识图谱构建工程师。
        
⚠️ 核心输出规则（不遵守将被判定为失败）：
1. 【详实正文】：在新建页面时，`content` 必须是包含3-4个段落的深度笔记，绝对不能只有一句话！
2. 【强制双链】：在 `abstract` 和 `content` 中，只要提到任何算法、模型、架构、术语或人名，**必须立即使用 [[ ]] 将其包裹！** - 正确：提出了一种基于 [[CNN]] 和 [[Dropout]] 的 [[目标检测]] 方法。
   - 错误：提出了一种基于CNN和Dropout的目标检测方法。
   - 目标：让你的正文里充满蓝色的 [[双向链接]]！
3. 【插队原则】：若触发 `create` 动作，必须紧跟一个 `append_link` 动作，将新建的 `[[概念]]` 追加到 index.md！
4. 【精准定位】：`old_str` 必须仅仅是 index.md 中的分类标题（例如 `## 核心算法`）！
        ✅ 【完整闭环示例】：
        {
          "new_concepts": ["Transformer"],
          "actions": [
            {
              "type": "create",
              "file": "concepts/transformer.md",
              "title": "Transformer",
              "tags": ["#architecture"],
              "abstract": "一种主要依赖于 [[Self-Attention]] 机制来处理时序数据的 [[深度学习]] 架构。",
              "content": "[[Transformer]] 完全抛弃了传统的 [[RNN]] 和 [[CNN]] 结构。\n\n它的核心是由 [[Encoder]] 和 [[Decoder]] 组成，并在其中大量使用了 [[多头注意力机制]] (Multi-Head Attention)。这种设计使得模型能够并行计算，极大提升了训练速度，并在 [[自然语言处理]] ([[NLP]]) 领域取得了突破性进展。\n\n相比于早期的 [[LSTM]]，它在解决长距离依赖问题上表现更好。",
              "rationale": "新建 Transformer 概念，包含丰富的双链和多段落解析"
            },
            {
              "type": "append_link",
              "file": "index.md",
              "old_str": "## 核心算法", 
              "link_to": "[[Transformer]]",
              "rationale": "追加到全局导航地图"
            }
          ]
        }
        """
        self.agent = Agent(
            model=get_qwen_model(),
            instructions=[self.instructions],
            output_schema=AnalysisReport,
            stream=False
        )

    def analyze(self, raw_text: str) -> dict:
        print("\n[WikiAnalyst] 正在读取全局地图并分析文本...")

        index_path = WIKI_ROOT / "index.md"
        index_content = index_path.read_text(encoding="utf-8") if index_path.exists() else "（当前知识库为空）"

        user_prompt = f"""
【全局导航地图 (index.md)】:
{index_content}

---
【新摄入的资料】:
{raw_text}

请严格按 JSON 格式输出，不要转义 Markdown 方括号。
"""
        response = self.agent.run(user_prompt)

        if isinstance(response.content, str):
            print("\n🚨 Pydantic 解析失败！原始字符串是：\n", response.content)
            raise ValueError("大模型未返回合法的 Pydantic 对象。")

        return response.content.model_dump()