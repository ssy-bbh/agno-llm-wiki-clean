# agents/web_researcher.py
from agno.agent import Agent
from core.llm_factory import get_qwen_model
from tools.search_tools import get_research_tools
from prompts.research_prompt import get_deep_research_instructions

def get_web_researcher():
    return Agent(
        name="Web Researcher",
        role="全网深度研究与情报分析专员",
        model=get_qwen_model(),
        tools=get_research_tools(),
        instructions=get_deep_research_instructions(),
        markdown=True,
        # 把 show_tool_calls=True 删掉，换成下面这行：
        debug_mode=True
    )