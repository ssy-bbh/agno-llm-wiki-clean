"""
wiki_writer.py — 知识撰稿人 (纯执行器)
"""
import re
from pathlib import Path
from tools.edit_tools import create_page, str_replace

class WikiWriter:
    def execute(self, report: dict) -> list[str]:
        print("\n[WikiWriter] 拿到分析报告，开始写盘...")
        actions = report.get("actions", [])
        results = []

        # 💡 内置归一化纯净器（无视空格、标点、大小写），用于同义词引力场
        def _norm(text):
            return re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', text).lower() if text else ""

        for action in actions:
            act_type = action.get("type")

            raw_file = action.get("file", "concepts/untitled.md")
            if not raw_file.startswith("concepts/") and raw_file != "index.md":
                raw_file = f"concepts/{raw_file}"

            target_path = Path(raw_file)

            if act_type == "create":
                # 保持安全的清洗和去空格
                title = (action.get("title") or target_path.stem).strip()
                safe_title = title.replace("/", "_").replace("\\", "_").replace(":", "_").replace("?", "_")
                perfect_file_name = f"{target_path.parent}/{safe_title}.md"

                res = create_page(
                    file_name=perfect_file_name,
                    title=title,
                    tags=action.get("tags", []),
                    abstract=action.get("abstract", ""),
                    content=action.get("content", "")
                )
                print(f"  -> {res}")
                results.append(res)

            elif act_type == "edit":
                if not target_path.exists():
                    # 💡 保留：同义词引力场 (模糊路径纠错)
                    target_norm = _norm(target_path.stem)
                    found_match = False

                    if target_path.parent.exists():
                        for existing_file in target_path.parent.glob("*.md"):
                            if _norm(existing_file.stem) == target_norm:
                                target_path = existing_file # 扭转路径至真实文件
                                print(f"  -> 🔍 纠错拦截：大模型路径存在幻觉，已强行重定向至真实文件 [{target_path.name}]")
                                found_match = True
                                break

                    # 💡 核心改变：如果同义词也没找到，直接拒绝！绝不自动创建！
                    if not found_match:
                        msg = f"  -> ❌ 严格模式拦截：找不到文件且无同义词匹配 ({target_path.name})，已强行丢弃此动作以防污染。"
                        print(msg)
                        results.append(msg)
                        continue

                # 正常替换逻辑
                old_str = action.get("old_str", "").replace("\\n", "\n")
                new_content = action.get("content", "").replace("\\n", "\n")

                res = str_replace(
                    file_name=str(target_path),
                    old_str=old_str,
                    new_str=new_content
                )
                print(f"  -> {res}")
                results.append(res)

            elif act_type == "extract_moc":
                old_str = action.get("old_str", "")
                moc_title = (action.get("title", "")).strip()
                moc_content = action.get("content", "")

                safe_title = moc_title.replace("/", "_").replace("\\", "_").replace(":", "_").replace("?", "_")
                moc_path = f"concepts/{safe_title}.md"

                res = create_page(
                    file_name=moc_path,
                    title=moc_title,
                    tags=["#MOC", "#导航地图"],
                    abstract=f"关于 {old_str.replace('#', '').strip()} 领域的知识汇聚与导航地图。",
                    content=moc_content
                )
                print(f"  -> 🌟 [细胞裂变] 成功创建子地图: {safe_title}.md")

                index_path = Path("index.md")
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
                        print(f"  -> 🏗️ 自动初始化缺失的导航文件: {target_path.name}")
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
                        res = str_replace(str(target_path), old_str, new_str)
                        print(f"  -> [导航地图更新] 追加 {single_link} 成功")
                        old_str = new_str
                        results.append(res)
            else:
                print(f" -> ⚠️ 暂未实现的操作类型: {act_type}")

        return results