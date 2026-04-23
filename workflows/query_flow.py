# workflows/query_flow.py
from agno.agent import Agent
from agno.team import Team
from agno.workflow import Workflow

# 👇 1. 绝不能漏的导包！确保大脑能正常供应
from core.llm_factory import get_qwen_model
from agents.local_wiki import get_local_wiki
from agents.web_researcher import get_web_researcher


def get_query_workflow():
    local_wiki = get_local_wiki()
    local_wiki.instructions = "处理本地知识库、VisionVoice、论文、笔记相关的检索。"

    web_researcher = get_web_researcher()
    web_researcher.instructions = "处理全网新闻、外部资讯的搜索。"

    # 2. 初始化时不传 model，避开可能的参数报错
    research_team = Team(
        name="Research Team",
        model=get_qwen_model(),
        members=[local_wiki, web_researcher],
        instructions=[
            "你负责数据收集和路由分发。",
            "如果用户询问本地资料或VisionVoice，请委派 Local Wiki 去查。",
            "如果用户询问外部新闻，请委派 Web Researcher 去查。",
            "将收集到的原始数据传递给下一个环节。"
        ]
    )

    # 👇 3. 核心修复：出生后再做“脑部移植”！强行给队长绑定 Qwen 模型
    research_team.model = get_qwen_model()

    # 下游的总结专员依然可以直接带脑子出生
    summarizer = Agent(
        name="Wiki Summarizer",
        model=get_qwen_model(),
        instructions="你是一个严谨的学术汇总专员。请根据上一个环节（Research Team）提供的数据，撰写排版精美、条理清晰的最终Markdown总结报告。"
    )

    return Workflow(
        name="Query Router Flow",
        description="意图路由与执行中枢",
        steps=[research_team, summarizer]
    )