"""
wiki_analyst.py — 知识分析师
执行摄入第一步：精读来源材料，与现有知识碰撞，输出结构化分析报告。
"""
from pathlib import Path
from typing import Optional
import json

from agents.local_wiki import get_local_wiki  # 复用现有 wiki agent 做向量检索

DATA_WIKI = Path(__file__).parent.parent / "data" / "wiki"
DATA_RAW = Path(__file__).parent.parent / "data" / "raw"


class WikiAnalyst:
    """知识分析师：只读不做写。"""

    def __init__(self):
        self.prompt = self._load_prompt()
        self.wiki_agent = get_local_wiki()

    def _load_prompt(self) -> str:
        from prompts.wiki_prompt import build_analyst_system_prompt
        return build_analyst_system_prompt()

    def ingest(
        self,
        source_file: str,
        context: Optional[str] = None,
    ) -> dict:
        """
        执行知识分析。

        Args:
            source_file: data/raw/ 下的文件名，如 "paper-attention-is-all.pdf"
            context:     可选，额外的上下文描述（如"这是 Transformer 论文"）

        Returns:
            JSON 格式的分析报告，参见 wiki_prompt.py 的输出格式定义
        """
        raw_path = DATA_RAW / source_file
        if not raw_path.exists():
            raise FileNotFoundError(f"来源文件不存在: {raw_path}")

        # 1. 读取来源
        content = self._read_source(raw_path)

        # 2. 读取必读清单
        index_md = (DATA_WIKI / "index.md").read_text(encoding="utf-8") if (DATA_WIKI / "index.md").exists() else ""
        log_md = (DATA_WIKI / "log.md").read_text(encoding="utf-8") if (DATA_WIKI / "log.md").exists() else ""

        # 3. 用 LLM 分析
        analysis_prompt = f"""## 来源材料

**文件**: {source_file}
**上下文**: {context or "（无）"}

**内容**:
{content[:8000]}

---

## data/wiki/index.md（全局导航地图）:
{index_md[:2000]}

---

## data/wiki/log.md（最新审计日志）:
{log_md[:1000]}

---

请按你的系统指令执行分析，输出 JSON 格式的分析报告。
"""
        # 调用 LLM（通过共享的 wiki_agent 的 model）
        response = self.wiki_agent.model_response(
            user_input=analysis_prompt,
            system_prompt=self.prompt,
        )
        return self._parse_response(response)

    def _read_source(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".md":
            return path.read_text(encoding="utf-8")
        elif suffix == ".pdf":
            try:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    return "\n".join(p.extract_text() or "" for p in pdf.pages)
            except ImportError:
                return "[PDF 读取需要 pip install pdfplumber]"
        elif suffix in (".png", ".jpg", ".jpeg"):
            return f"[图片文件，需 OCR: {path.name}]"
        else:
            return path.read_text(encoding="utf-8", errors="replace")

    def _parse_response(self, response: str) -> dict:
        # 尝试提取 JSON 块
        import re
        match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        # fallback：直接解析
        return json.loads(response)
