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
        # 💡 升级了紧箍咒：强调 tags 格式并严禁转义
        self.instructions = """你是一个严谨的知识分析师。

⚠️ 严格警告与核心决策规则：
1. 【插队更新】：如果你决定新建概念（create），必须紧接着输出 `append_link` 动作，将其双向链接追加到 index.md 的对应分类下！
2. 【严格列表】：`tags` 字段必须是 JSON 数组（如 `["#tag"]`），绝不能是字符串！
3. 【禁止转义】：在输出 `old_str` 和 `link_to` 时，绝对保留原始的 Markdown 格式！不要把 `[[概念]]` 转义成 `\\[\\[概念\\]\\]`！

✅ 【完整闭环示例】：
{
  "new_concepts": ["Transformer"],
  "actions": [
    {
      "type": "create",
      "file": "concepts/transformer.md",
      "title": "Transformer",
      "tags": ["#architecture"],
      "abstract": "一种处理时序数据的架构。",
      "rationale": "新建 Transformer 概念"
    },
    {
      "type": "append_link",
      "file": "index.md",
      "old_str": "## 核心算法\\n- [[YOLOv8]]",
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