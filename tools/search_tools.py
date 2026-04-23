# tools/search_tools.py
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.newspaper4k import Newspaper4kTools

def get_research_tools():
    """
    统一管理并返回深度研究所需的工具包。
    未来如果需要改用 Google Search 或 Bing，只需在此替换即可，Agent 代码无需变动。
    """
    return [DuckDuckGoTools(), Newspaper4kTools()]