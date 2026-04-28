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
                original_file = action.get("file", "concepts/untitled.md")
                title = action.get("title", "未命名")

                # 💡 终极修复：强制“物理文件名”与“展示标题”绝对一致！
                # 无论大模型吐出的 file 是 fast_r_cnn.md 还是什么，
                # 我们强行把它替换成 Fast R-CNN.md，以完美适配 Obsidian 的双链规则。
                from pathlib import Path
                dir_name = Path(original_file).parent
                # 移除非法路径字符，防止报错
                safe_title = title.replace("/", "_").replace("\\", "_").replace(":", "_").replace("?", "_")
                # 拼装出真正完美的文件路径
                perfect_file_name = f"{dir_name}/{safe_title}.md"

                res = create_page(
                    file_name=perfect_file_name,
                    title=title,
                    tags=action.get("tags", []),
                    abstract=action.get("abstract", ""),
                    content=action.get("content", "")
                )
                print(f"  -> {res}")
                results.append(res)

            # 💡 新增的 edit 分支
            elif act_type == "edit":
                old_str = action.get("old_str", "").replace("\\n", "\n")
                new_content = action.get("content", "").replace("\\n", "\n")

                res = str_replace(
                    file_name=file_name,
                    old_str=old_str,
                    new_str=new_content
                )



            elif act_type == "append_link":

                old_str = action.get("old_str")

                raw_link_to = str(action.get("link_to", ""))

                if old_str and raw_link_to:

                    from tools.edit_tools import _resolve, str_replace

                    import re

                    target_path = _resolve(file_name)

                    # 💡 1. 暴力清洗：把大模型吐出的乱七八糟的字符串，提取成干净的单链数组

                    links = re.findall(r'\[\[.*?\]\]', raw_link_to)

                    if not links:

                        # 如果大模型连括号都忘了打，我们强行帮它套上

                        clean_name = raw_link_to.replace("[", "").replace("]", "").replace('"', "").replace("'",
                                                                                                            "").strip()

                        if clean_name:
                            links = [f"[[{clean_name}]]"]

                    if target_path.exists():

                        content = target_path.read_text(encoding="utf-8")

                        # 💡 2. 遍历提取出的每一个独立链接

                        for single_link in links:

                            # 将准备追加的链接“暴力去噪”（去空格、去符号、转小写）

                            clean_target = single_link.lower().replace("-", "").replace("_", "").replace(" ", "")

                            # 获取地图里已经存在的所有链接

                            existing_links = re.findall(r'\[\[(.*?)\]\]', content)

                            is_duplicate = False

                            for ex_link in existing_links:

                                clean_ex = f"[[{ex_link}]]".lower().replace("-", "").replace("_", "").replace(" ", "")

                                # 💡 模糊相似度拦截！如果发现存在 FastR-CNN，就拒绝追加 Fast R-CNN

                                if clean_target == clean_ex:
                                    print(f"  -> ⏭️ 拦截相似：导航地图已存在 [[{ex_link}]]，跳过追加 {single_link}。")

                                    is_duplicate = True

                                    break

                            if is_duplicate:
                                continue

                            # 💡 3. 安全追加：每次只老老实实追加一行

                            new_str = f"{old_str}\n- {single_link}"

                            res = str_replace(file_name, old_str, new_str)

                            print(f"  -> [导航地图更新] 追加 {single_link} 成功")

                            # 重要：更新 old_str，这样如果这批有多个链接，它们会乖乖排在下面

                            old_str = new_str
            else:

                print(f" -> ⚠️ 暂未实现的操作类型: {act_type}")

        return results

