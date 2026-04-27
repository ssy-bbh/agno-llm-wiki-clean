"""
wiki_writer.py — 知识撰稿人 (纯执行器)
"""
from tools.edit_tools import create_page, str_replace


class WikiWriter:
    def execute(self, report: dict) -> list[str]:
        print("\n[WikiWriter] 拿到分析报告，开始写盘...")
        actions = report.get("actions", [])
        results = []

        for action in actions:
            act_type = action.get("type")
            file_name = action.get("file", "")

            if act_type == "create":
                res = create_page(
                    file_name=file_name,
                    title=action.get("title", "未命名"),
                    tags=action.get("tags", []),
                    abstract=action.get("abstract", "")
                )
                print(f" -> {res}")
                results.append(res)

            # 💡 新增的 edit 分支
            elif act_type == "edit":
                # 💡 魔法修复：将 JSON 字符串里的字面量 "\\n" 还原为真正的换行符
                old_str = action.get("old_str", "").replace("\\n", "\n")
                new_content = action.get("content", "").replace("\\n", "\n")

                res = str_replace(
                    file_name=file_name,
                    old_str=old_str,
                    new_str=new_content
                )

            else:
                print(f" -> ⚠️ 暂未实现的操作类型: {act_type}")

        return results