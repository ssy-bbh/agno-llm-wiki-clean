"""
wiki_writer.py — 知识撰稿人
执行摄入第二步：接收分析报告，调用 edit_tools 执行具体的磁盘写入。
"""
from pathlib import Path
from typing import Optional

DATA_WIKI = Path(__file__).parent.parent / "data" / "wiki"


class WikiWriter:
    """知识撰稿人：只写不分析。"""

    def __init__(self):
        self._load_prompt()

    def _load_prompt(self) -> str:
        from prompts.wiki_prompt import build_writer_system_prompt
        return build_writer_system_prompt()

    def apply(self, report: dict) -> list[str]:
        """
        根据 wiki_analyst 的分析报告，执行磁盘写入。

        Args:
            report: wiki_analyst 输出的 JSON 报告

        Returns:
            操作结果列表
        """
        from tools.edit_tools import (
            str_replace,
            append_to_log,
            create_page,
        )

        results = []
        actions = report.get("actions", [])

        for action in actions:
            act_type = action.get("type", "")
            file = action.get("file", "")
            content = action.get("content", "")
            rationale = action.get("rationale", "")

            try:
                if act_type == "create":
                    # 从文件名推断目录
                    if "/" not in file:
                        file = "concepts/" + file
                    title = content.split("\n")[0].lstrip("#").strip()
                    tags = self._extract_tags(content)
                    abstract = self._extract_abstract(content)
                    result = create_page(
                        file_name=file.split("/")[-1],
                        template="concept",
                        title=title,
                        tags=tags,
                        abstract=abstract,
                    )
                    results.append(result)

                elif act_type == "edit":
                    old_str = action.get("old_str", "")
                    if not old_str:
                        results.append(f"⚠️ edit 操作缺少 old_str: {file}")
                        continue
                    result = str_replace(file, old_str, content)
                    results.append(result)

                elif act_type == "append_link":
                    # 在 Related 节追加 [[link]]
                    old_str = action.get("old_str", "")
                    link_to = action.get("link_to", "")
                    new_str = old_str + f"\n- {link_to}"
                    if old_str:
                        result = str_replace(file, old_str, new_str)
                        results.append(result)
                    else:
                        # 找到 Related 节追加
                        pass

                else:
                    results.append(f"⚠️ 未知操作类型: {act_type}")

                # 审计日志
                append_to_log(f"{act_type.upper()} | {file} | {rationale}")

            except Exception as e:
                msg = f"❌ {file}: {e}"
                results.append(msg)
                append_to_log(f"ERROR | {file} | {e}")

        return results

    def _extract_tags(self, content: str) -> list[str]:
        import re
        tags = re.findall(r"#[\w-]+", content)
        return tags[:5]

    def _extract_abstract(self, content: str) -> str:
        """从 content 中提取 Abstract 节内容。"""
        import re
        m = re.search(r"## Abstract\s*\n+(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if m:
            return m.group(1).strip()[:200]
        return ""
