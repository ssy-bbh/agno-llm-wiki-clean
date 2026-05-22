"""
wiki_writer.py — 知识撰稿人 (活路径雷达 + 严格写盘版)
"""
import re
from tools.edit_tools import _resolve, create_page, str_replace

class WikiWriter:
    def execute(self, report: dict) -> list[str]:
        print("\n[WikiWriter] 拿到分析报告，开始物理写盘...")
        actions = report.get("actions", [])
        results = []

        def _is_same_concept(name1, name2):
            """聪明且克制的集合交集防撞雷达"""

            def _get_aliases(text: str) -> set:
                aliases = set()
                # 1. 整体纯净版
                clean_text = text.lower().replace("-", "").replace("_", "").replace(" ", "")
                if clean_text: aliases.add(clean_text)

                # 2. 括号双语解构版
                match = re.match(r'^(.*?)\s*[\(（](.*?)[\)）]', text)
                if match:
                    part1 = match.group(1).lower().replace("-", "").replace("_", "").replace(" ", "")
                    part2 = match.group(2).lower().replace("-", "").replace("_", "").replace(" ", "")
                    if part1: aliases.add(part1)
                    if part2: aliases.add(part2)
                return aliases

            # 只有两个名字的别名集合有交集，才算是同一个概念
            return bool(_get_aliases(name1) & _get_aliases(name2))

        for action in actions:
            act_type = action.get("type")

            raw_file = action.get("file", "concepts/untitled.md")
            if not raw_file.startswith("concepts/") and raw_file != "index.md":
                raw_file = f"concepts/{raw_file}"

            # 💡 核心修复 1：使用 _resolve() 计算出最终活路径，雷达扫描必须基于真实路径！
            target_path = _resolve(raw_file)

            if act_type == "create":
                title = (action.get("title") or target_path.stem).strip()
                safe_title = title.replace("/", "_").replace("\\", "_").replace(":", "_").replace("?", "_")

                # 重新计算一次最标准的真实路径，防止大模型名字给得不规范
                perfect_raw_file = f"concepts/{safe_title}.md"
                perfect_target_path = _resolve(perfect_raw_file)

                # 🛡️ 物理拦截雷达启动（基于真实目标目录）
                found_existing = None
                if perfect_target_path.parent.exists():
                    for existing_file in perfect_target_path.parent.glob("*.md"):
                        if _is_same_concept(existing_file.stem, title):
                            found_existing = existing_file
                            break

                if found_existing:
                    print(f"  -> 🛡️ 拦截创建冲突：同义词文件 [{found_existing.name}] 已存在，自动转为 [增量追加]...")

                    # 💡 核心修复 2：将换行符替换抽出，避开 Python 3.11 的 f-string 报错
                    safe_new_content = action.get("content", "").replace("\\n", "\n")
                    updated_content = found_existing.read_text(encoding="utf-8") + f"\n\n---\n### 🧠 增量融合视角 ({title})\n{safe_new_content}\n"
                    found_existing.write_text(updated_content, encoding="utf-8")

                    results.append(f"成功合并至: {found_existing.name}")
                    continue

                # 工具层依然接收相对的 perfect_raw_file 即可，里面会再次 _resolve
                res = create_page(perfect_raw_file, title, action.get("tags", []), action.get("abstract", ""), action.get("content", ""))
                print(f"  -> {res}")
                results.append(res)

            elif act_type == "edit":
                if not target_path.exists():
                    found_match = False
                    if target_path.parent.exists():
                        for existing_file in target_path.parent.glob("*.md"):
                            if _is_same_concept(existing_file.stem, target_path.stem):
                                target_path = existing_file
                                # 扭转相对路径，供底层工具使用
                                raw_file = f"concepts/{existing_file.name}" if raw_file != "index.md" else "index.md"
                                print(f"  -> 🔍 纠错重定向：大模型编辑路径存在幻觉，已自动扭转至真实物理文件 [{target_path.name}]")
                                found_match = True
                                break

                    if not found_match:
                        msg = f"  -> ❌ 严格模式拦截：找不到编辑目标 ({target_path.name})，已丢弃动作。"
                        print(msg)
                        results.append(msg)
                        continue

                res = str_replace(raw_file, action.get("old_str", "").replace("\\n", "\n"), action.get("content", "").replace("\\n", "\n"))
                print(f"  -> {res}")
                results.append(res)

            elif act_type == "extract_moc":
                old_str = action.get("old_str", "")
                moc_title = (action.get("title", "")).strip()
                moc_content = action.get("content", "")

                safe_title = moc_title.replace("/", "_").replace("\\", "_").replace(":", "_").replace("?", "_")
                moc_raw_path = f"concepts/{safe_title}.md"

                res = create_page(moc_raw_path, moc_title, ["#MOC", "#导航地图"], f"关于 {old_str.replace('#', '').strip()} 领域的知识汇聚与导航地图。", moc_content)
                print(f"  -> 🌟 [细胞裂变] 成功创建子地图: {safe_title}.md")

                # 💡 核心修复 3：精准获取真实活路径下的 index.md
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
                    print(f"  -> ✂️ [精细截断] index.md 导航地图已自动折叠至 [[{moc_title}]]")

            elif act_type == "append_link":
                old_str = action.get("old_str")
                raw_link_to = str(action.get("link_to", ""))

                if old_str and raw_link_to:
                    links = re.findall(r'\[\[.*?\]\]', raw_link_to)
                    if not links:
                        clean_name = raw_link_to.replace("[", "").replace("]", "").replace('"', "").replace("'", "").strip()
                        if clean_name:
                            links = [f"[[{clean_name}]]"]

                    if not target_path.exists():
                        folder_name = target_path.parent.name if target_path.parent.name else "全局"
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        target_path.write_text(f"# {folder_name} 知识导航\n\n{old_str}\n", encoding="utf-8")

                    content = target_path.read_text(encoding="utf-8")
                    if old_str not in content:
                        content += f"\n\n{old_str}\n"
                        target_path.write_text(content, encoding="utf-8")
                        content = target_path.read_text(encoding="utf-8")

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

                        new_str = f"{old_str}\n- {single_link}"
                        # 确保交给工具的是相对路径，由 _resolve 接管
                        res = str_replace(raw_file, old_str, new_str)
                        print(f"  -> [导航地图更新] 追加 {single_link} 成功")
                        old_str = new_str
                        results.append(res)
            else:
                print(f" -> ⚠️ 暂未实现的操作类型: {act_type}")

        return results