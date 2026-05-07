"""
wiki_writer.py — 知识撰稿人 (纯执行器)
"""
import re
from pathlib import Path
from tools.edit_tools import _resolve, create_page, str_replace

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
                dir_name = Path(original_file).parent
                safe_title = title.replace("/", "_").replace("\\", "_").replace(":", "_").replace("?", "_")
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

            # 💡 edit 分支：补齐了日志打印和结果录入
            elif act_type == "edit":
                old_str = action.get("old_str", "").replace("\\n", "\n")
                new_content = action.get("content", "").replace("\\n", "\n")

                res = str_replace(
                    file_name=file_name,
                    old_str=old_str,
                    new_str=new_content
                )
                print(f"  -> {res}")
                results.append(res)

            # 💡 MOC 裂变机制
            elif act_type == "extract_moc":
                old_str = action.get("old_str", "")
                moc_title = action.get("title", "")
                moc_content = action.get("content", "")

                safe_title = moc_title.replace("/", "_").replace("\\", "_").replace(":", "_").replace("?", "_")
                res = create_page(
                    file_name=str(_resolve(f"concepts/{safe_title}.md")),
                    title=moc_title,
                    tags=["#MOC", "#导航地图"],
                    abstract=f"关于 {old_str.replace('#', '').strip()} 领域的知识汇聚与导航地图。",
                    content=moc_content
                )
                print(f"  -> 🌟 [细胞裂变] 成功创建子地图: {safe_title}.md")

                index_path = _resolve("index.md")
                if index_path.exists():
                    content = index_path.read_text(encoding="utf-8")
                    lines = content.split('\n')
                    new_lines = []
                    in_target_section = False
                    replaced = False

                    for line in lines:
                        if line.strip() == old_str.strip():
                            in_target_section = True
                            new_lines.append(line)
                            continue

                        if in_target_section:
                            if line.startswith('#'):
                                in_target_section = False
                                new_lines.append(line)
                            elif line.strip().startswith('- [[') or line.strip().startswith('* [['):
                                if not replaced:
                                    new_lines.append(f"- [[{moc_title}]]")
                                    replaced = True
                            else:
                                new_lines.append(line)
                        else:
                            new_lines.append(line)

                    index_path.write_text('\n'.join(new_lines), encoding="utf-8")
                    msg = f"✂️ [精细截断] index.md 导航地图已自动折叠至 [[{moc_title}]]"
                    print(f"  -> {msg}")
                    results.append(msg)

            elif act_type == "append_link":
                old_str = action.get("old_str")
                raw_link_to = str(action.get("link_to", ""))

                if old_str and raw_link_to:
                    target_path = _resolve(file_name)

                    # 1. 暴力清洗
                    links = re.findall(r'\[\[.*?\]\]', raw_link_to)
                    if not links:
                        clean_name = raw_link_to.replace("[", "").replace("]", "").replace('"', "").replace("'", "").strip()
                        if clean_name:
                            links = [f"[[{clean_name}]]"]

                    # 2. 终极修复：无中生有大魔法！
                    if not target_path.exists():
                        print(f"  -> 🏗️ 自动初始化缺失的导航文件: {target_path.name}")
                        folder_name = target_path.parent.name if target_path.parent.name else "全局"
                        target_path.write_text(f"# {folder_name} 知识导航\n\n{old_str}\n", encoding="utf-8")

                    # 补漏
                    content = target_path.read_text(encoding="utf-8")
                    if old_str not in content:
                        content += f"\n\n{old_str}\n"
                        target_path.write_text(content, encoding="utf-8")
                        content = target_path.read_text(encoding="utf-8")

                    # 3. 遍历提取
                    for single_link in links:
                        clean_target = single_link.lower().replace("-", "").replace("_", "").replace(" ", "")
                        existing_links = re.findall(r'\[\[(.*?)\]\]', content)
                        is_duplicate = False

                        for ex_link in existing_links:
                            clean_ex = f"[[{ex_link}]]".lower().replace("-", "").replace("_", "").replace(" ", "")
                            if clean_target == clean_ex:
                                print(f"  -> ⏭️ 拦截相似：导航地图已存在 [[{ex_link}]]，跳过追加。")
                                is_duplicate = True
                                break

                        if is_duplicate:
                            continue

                        # 4. 安全追加
                        new_str = f"{old_str}\n- {single_link}"
                        res = str_replace(file_name, old_str, new_str)
                        print(f"  -> [导航地图更新] 追加 {single_link} 成功")
                        old_str = new_str
                        results.append(res)  # 💡 这里也顺手把结果收集起来

            else:
                print(f" -> ⚠️ 暂未实现的操作类型: {act_type}")

        return results