# 增加 field_validator 和 Any 的导入
from pydantic import BaseModel, Field, field_validator
from typing import List, Any, Optional
from agno.agent import Agent
from core.llm_factory import get_qwen_model


class Action(BaseModel):
    type: str = Field(description="操作类型：'create' 或 'edit'")
    file: str = Field(description="文件路径，例如 concepts/yolov8.md")

    # --- Create 专属字段（改为可选） ---
    title: Optional[str] = Field(default=None, description="页面的核心标题")
    tags: Optional[List[str]] = Field(default=None, description="标签列表")
    abstract: Optional[str] = Field(default=None, description="摘要")

    # --- Edit 专属字段（新增且可选） ---
    old_str: Optional[str] = Field(default=None, description="需要被精确替换的旧文本原文")
    content: Optional[str] = Field(default=None, description="替换后的新文本内容")

    # --- 通用字段 ---
    rationale: str = Field(description="操作理由")

    @field_validator('tags', mode='before')
    @classmethod
    def ensure_list(cls, v: Any):
        if isinstance(v, str):
            return [tag.strip() for tag in v.split(',') if tag.strip()]
        return v


class AnalysisReport(BaseModel):
    new_concepts: List[str] = Field(description="提取出的核心概念名称列表")
    actions: List[Action] = Field(description="执行动作列表")


class WikiAnalyst:
    def __init__(self):
        # 💡 新增了【双向链接规则】和对应的示例
        self.instructions = """你是一个严谨的知识分析师。你的任务是提取文本中的核心概念，并生成对 Wiki 页面的操作指令。

⚠️ 严格警告：你必须且只能输出合法的 JSON，严格遵守 Pydantic 的 Schema！
💡 核心规则【双向链接】：在你编写的 `abstract` 或 `content` 中，只要提到了其他重要的实体、算法或概念（比如你刚提取到 new_concepts 里的词），必须使用双向链接语法将其包裹，即 `[[概念名称]]`！

✅ 【正确示例】：
{
  "new_concepts": ["端侧AI", "YOLOv8"],
  "actions": [
    {
      "type": "create",
      "file": "concepts/vision-voice.md",
      "title": "VisionVoice",
      "tags": ["#mobile-app"],
      "abstract": "一款基于 [[端侧AI]] 的实时目标识别应用，其底层视觉引擎使用了量化后的 [[YOLOv8]] 模型。",
      "rationale": "创建项目主页，并关联核心技术"
    },
    {
      "type": "edit",
      "file": "concepts/yolov8.md",
      "old_str": "## Details\\n（等待后续扩展）",
      "content": "## Details\\n团队成功将 [[YOLOv8]] 部署到了 iPad 上，极大地增强了 [[端侧AI]] 的推理效率。",
      "rationale": "补充了 YOLOv8 的端侧部署细节"
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

    # 下面的 analyze 方法保持不变...

    def analyze(self, raw_text: str) -> dict:
        print("\n[WikiAnalyst] 正在分析文本并强制校验 JSON 格式...")

        # 2. 用户提示词极其精简，不给大模型任何发散的机会
        user_prompt = f"请分析以下来源材料，并严格填充你的 JSON 模板：\n{raw_text}"
        response = self.agent.run(user_prompt)

        # 3. 增加类型保护：如果 Pydantic 依然解析失败，把大模型的原话打出来看看
        if isinstance(response.content, str):
            print("\n🚨 Pydantic 解析失败！大模型返回的原始字符串是：")
            print(response.content)
            raise ValueError("大模型未返回合法的 Pydantic 对象。")

        # 走到这里说明 100% 成功了
        report_obj = response.content
        return report_obj.model_dump()