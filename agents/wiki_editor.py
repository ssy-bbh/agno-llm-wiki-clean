"""
wiki_editor.py — 知识主编 (比对与决策)
"""
import json
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Any, Optional, Literal
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from agno.agent import Agent
from core.llm_factory import get_qwen_model

# 单次 LLM 调用超时（秒）——融合比提取更复杂，给更多时间
LLM_TIMEOUT_SECONDS = 300


# 💡 我们把 Action 的定义移交给了主编，因为只有它才有权下达动作指令
class Action(BaseModel):
    type: Literal["create", "edit", "append_link", "extract_moc"] = Field(description="必须严格使用这四个词之一")
    file: str = Field(description="文件路径")
    title: Optional[str] = Field(default=None)
    tags: Optional[List[str]] = Field(default=None)
    abstract: Optional[str] = Field(default=None)
    old_str: Optional[str] = Field(default=None)
    content: Optional[str] = Field(default=None)
    link_to: Optional[str] = Field(default=None)
    rationale: str = Field(description="操作理由")

    @model_validator(mode='before')
    @classmethod
    def fix_llm_field_names(cls, data: Any) -> Any:
        """容错：LLM 偶尔用 action/target/reason 代替 type/file/rationale"""
        if isinstance(data, dict):
            # action → type
            if 'action' in data and 'type' not in data:
                data['type'] = data.pop('action')
            # target → file
            if 'target' in data and 'file' not in data:
                data['file'] = data.pop('target')
            # reason/reasoning → rationale
            if 'reason' in data and 'rationale' not in data:
                data['rationale'] = data.pop('reason')
            elif 'reasoning' in data and 'rationale' not in data:
                data['rationale'] = data.pop('reasoning')
            # description → rationale (fallback)
            if 'description' in data and 'rationale' not in data:
                data['rationale'] = data.pop('description')
            # 兜底：如果 rationale 仍然缺失，给个默认值
            if 'rationale' not in data:
                data['rationale'] = 'LLM 未提供理由'
        return data

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
        6. 【渐进式披露 (extract_moc)】（最高警戒）：在修改 `index.md` 时，必须时刻监控信息密度！
           - ⚡ 触发条件：当你准备向 `index.md` 的某个 `### 标题` 下追加链接时，如果发现该标题下现有的 `[[具体知识点]]` 链接数量达到或超过 7 个，你绝对不能继续使用 'append_link'！
           - 🛠️ 强制动作：你必须改为输出 'extract_moc' 动作，将该标题下的所有旧链接与你的新链接，一起打包提取为一个独立的 MOC (导航地图) 文件。
           - `old_str`：必须包含该标题和下方所有的旧链接（用于底层的雷达精确锁定与折叠）。
           - `title`：新子地图的名称（如 "YOLO系列演进 MOC"）。
           - `content`：新子地图的完整正文（包含领域摘要、分类标题以及所有的具体链接）。
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
        # 超时保护：防止单个概念融合卡住导致整个流水线停滞
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.agent.run, user_prompt)
            try:
                response = future.result(timeout=LLM_TIMEOUT_SECONDS)
            except FuturesTimeoutError:
                print(f"\n⏰ [WikiEditor] LLM 调用超时 ({LLM_TIMEOUT_SECONDS}s)，跳过此概念")
                return {"actions": []}  # 返回空动作 = 跳过写盘

        if isinstance(response.content, str):
            # 🔧 JSON 修复兆底：手动修正 LLM 常用的错误字段名
            raw = response.content.strip()
            # 提取 JSON 块
            if '```json' in raw:
                raw = raw.split('```json', 1)[1].split('```', 1)[0].strip()
            elif '```' in raw:
                raw = raw.split('```', 1)[1].split('```', 1)[0].strip()
            try:
                data = json.loads(raw)
                # 修复每个 action 的字段名
                for act in data.get('actions', []):
                    if 'action' in act and 'type' not in act:
                        act['type'] = act.pop('action')
                    if 'target' in act and 'file' not in act:
                        act['file'] = act.pop('target')
                    if 'reason' in act and 'rationale' not in act:
                        act['rationale'] = act.pop('reason')
                    elif 'reasoning' in act and 'rationale' not in act:
                        act['rationale'] = act.pop('reasoning')
                    elif 'description' in act and 'rationale' not in act:
                        act['rationale'] = act.pop('description')
                    if 'rationale' not in act:
                        act['rationale'] = 'LLM 未提供理由'
                report = EditorReport.model_validate(data)
                print(f"  🔧 JSON 修复成功，恢复 {len(report.actions)} 个 actions")
                return report.model_dump()
            except Exception as fix_err:
                print(f"  ❌ JSON 修复失败: {fix_err}")
                raise ValueError("大模型未返回合法的 Pydantic 对象。")

        return response.content.model_dump()