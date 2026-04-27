# 增加 field_validator 和 Any 的导入
from pydantic import BaseModel, Field, field_validator
from typing import List, Any
from agno.agent import Agent
from core.llm_factory import get_qwen_model

class Action(BaseModel):
    type: str = Field(description="操作类型，目前固定为 'create'")
    file: str = Field(description="文件路径，例如 concepts/vision-voice.md")
    title: str = Field(description="页面的核心标题")
    tags: List[str] = Field(description="标签列表，例如 ['#ai', '#yolov8']")
    abstract: str = Field(description="用 2-3 句话总结这个概念的摘要")
    rationale: str = Field(description="为什么要创建这个页面的理由")

    # 💡 魔法拦截器：专门对付大模型把 List 写成 String 的偷懒行为
    @field_validator('tags', mode='before')
    @classmethod
    def ensure_list(cls, v: Any):
        if isinstance(v, str):
            # 如果是字符串 "#ai, #mobile-app"，自动按逗号切分并清理两边空格
            return [tag.strip() for tag in v.split(',') if tag.strip()]
        return v

# 下面的 AnalysisReport 和 WikiAnalyst 保持不变...

class AnalysisReport(BaseModel):
    new_concepts: List[str] = Field(description="提取出的核心概念名称列表")
    actions: List[Action] = Field(description="执行动作列表")


class WikiAnalyst:
    def __init__(self):
        # 1. 带有明确 JSON 示例的指令（彻底封死大模型的想象力）
        self.instructions = """你是一个严谨的知识分析师。你的任务是提取文本中的核心概念，并生成**创建 Wiki 页面**的指令。

⚠️ 严格警告：你必须输出合法的 JSON，并且结构必须与下面的【正确示例】一模一样！
- `new_concepts` 只能是纯字符串列表，不能是字典！
- `actions` 是建立文件的动作，绝不是描述软件功能！必须严格包含 type, file, title, tags, abstract, rationale 字段！

✅ 【正确示例】：
{
  "new_concepts": ["VisionVoice", "YOLOv8"],
  "actions": [
    {
      "type": "create",
      "file": "concepts/vision-voice.md",
      "title": "VisionVoice",
      "tags": ["#ai", "#mobile-app"],
      "abstract": "一款基于端侧 AI 的实时目标识别与发音训练应用。",
      "rationale": "文本提到了这个核心应用，需要为其建立独立概念页"
    },
    {
      "type": "create",
      "file": "concepts/yolov8.md",
      "title": "YOLOv8",
      "tags": ["#algorithm", "#object-detection"],
      "abstract": "一种目标检测模型，在项目中被量化以适应端侧设备。",
      "rationale": "提取到了核心底层算法"
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