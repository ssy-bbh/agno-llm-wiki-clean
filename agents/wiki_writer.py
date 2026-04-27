"""
wiki_writer.py — 知识撰稿人 (纯执行器)
"""
from tools.edit_tools import create_page


class WikiWriter:
    """只写不分析的无情机器"""

    def execute(self, report: dict) -> list[str]:
        print("\n[WikiWriter] 拿到分析报告，开始写盘...")
        actions = report.get("actions", [])
        results = []

        for action in actions:
            act_type = action.get("type")

            if act_type == "create":
                # 直接从 JSON 里提取我们规范好的字段
                res = create_page(
                    file_name=action.get("file", ""),
                    title=action.get("title", "未命名"),
                    tags=action.get("tags", []),
                    abstract=action.get("abstract", "")
                )
                print(f" -> {res}")
                results.append(res)
            else:
                print(f" -> ⚠️ 暂未实现的操作类型: {act_type}")

        return results