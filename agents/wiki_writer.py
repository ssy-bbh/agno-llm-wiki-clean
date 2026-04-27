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

                # 💡 优雅的新增逻辑：复用手术刀实现精准插队

            elif act_type == "append_link":

                old_str = action.get("old_str", "").replace("\\n", "\n")

                link_to = action.get("link_to", "")

                # 巧妙拼接：把新链接追加到旧字符串的下一行

                new_content = f"{old_str}\n- {link_to}"

                res = str_replace(

                    file_name=file_name,

                    old_str=old_str,

                    new_str=new_content

                )

                print(f" -> [导航地图更新] {res}")

                results.append(res)


            else:

                print(f" -> ⚠️ 暂未实现的操作类型: {act_type}")

        return results

