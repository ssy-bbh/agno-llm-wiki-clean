"""
wiki_writer.py — 知识撰稿人 (纯执行器 - 双轨骨架拦截+严格写盘完全版)
"""
import re
from pathlib import Path
from tools.edit_tools import create_page, str_replace

class WikiWriter:
    def execute(self, report: dict) -> list[str]:
        print("\n[WikiWriter] 拿到分析报告，开始物理写盘...")
        actions = report.get("actions", [])
        results = []

        # 💡 内置双轨归一化纯净器：用于在最底层物理落盘的最后一纳秒拦截同义词与时差冲突
        def _is_same_concept(name1, name2):
            # 提取纯英文和数字骨架
            eng1 = re.sub(r'[^a-zA-Z0-9]', '', name1).lower()
            eng2 = re.sub(r'[^a-zA-Z0-9]', '', name2).lower()
            # 提取纯中文骨架
            zh1 = re.sub(r'[^\u4e00-\u9fa5]', '', name1)
            zh2 = re.sub(r'[^\u4e00-\u9fa5]', '', name2)

            # 条件1：英文骨架互相包含（至少3个字母防误伤）
            match_eng = bool(eng1 and eng2) and (eng1 in eng2 or eng2 in eng1) and min(len(eng1), len(eng2)) >= 3
            # 条件2：中文骨架互相包含（至少2个汉字防误伤）
            match_zh = bool(zh1 and zh2) and (zh1 in zh2 or zh2 in zh1) and min(len(zh1), len(zh2)) >= 2

            return match_eng or match_zh

        for action in actions:
            act_type = action.get("type")

            # 智能路径寻址：大模型如果丢了 concepts/ 前缀，在这里自动补齐
            raw_file = action.get("file", "concepts/untitled.md")
            if not raw_file.startswith("concepts/") and raw_file != "index.md":
                raw_file = f"concepts/{raw_file}"

            # 坚决不使用外部重定向工具，直接锁定本地原生 Path
            target_path = Path(raw_file)

            if act_type == "create":
                # 强力清除首尾空格，消灭 "Label Smoothing .md" 这种幻觉
                title = (action.get("title") or target_path.stem).strip()
                safe_title = title.replace("/", "_").replace("\\", "_").replace(":", "_").replace("?", "_")
                perfect_file_name = f"{target_path.parent}/{safe_title}.md"

                # 🛡️ 最后一纳秒的物理拦截雷达：即使模型发出 create 指令，也必须检索是否有同义词已落盘
                found_existing = None
                if target_path.parent.exists():
                    for existing_file in target_path.parent.glob("*.md"):
                        if _is_same_concept(existing_file.stem, title):
                            found_existing = existing_file
                            break

                # 🚨 触发时差冲突拦截：前序并发任务已经把同义词文件抢先写入了！
                if found_existing:
                    print(f"  -> 🛡️ 拦截物理创建冲突：同义词文件 [{found_existing.name}] 已被前序任务抢先写盘！")
                    print(f"     物理层自动将 [create] 扭转为 [增量追加] 模式，防止文件分裂...")

                    old_content = found_existing.read_text(encoding="utf-8")
                    new_content = action.get("content", "").replace("\\n", "\n")

                    # 极其安全地以 Markdown 形式追加，绝对不丢失、不覆盖、不分裂
                    updated_content = old_content + f"\n\n---\n### 🧠 增量融合视角 ({title})\n{new_content}\n"
                    found_existing.write_text(updated_content, encoding="utf-8")

                    msg = f"成功在物理层拦截冲突，增量内容已安全追加至: {found_existing.name}"
                    results.append(msg)
                    continue

                # 如果确实是无冲突的纯新概念，执行正常创建
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
                # 严格写盘模式：如果文件在硬盘上不存在，先尝试用双轨骨架纠错重定向
                if not target_path.exists():
                    found_match = False
                    if target_path.parent.exists():
                        for existing_file in target_path.parent.glob("*.md"):
                            if _is_same_concept(existing_file.stem, target_path.stem):
                                target_path = existing_file
                                print(f"  -> 🔍 纠错重定向：大模型编辑路径存在幻觉，已自动扭转至真实物理文件 [{target_path.name}]")
                                found_match = True
                                break

                    # 如果连同义词骨架也对不上，说明模型彻底胡编了一个不存在的文件，无情拦截，绝不降级创建！
                    if not found_match:
                        msg = f"  -> ❌ 严格模式拦截：找不到编辑目标且无同义词匹配 ({target_path.name})，已丢弃动作以防污染。"
                        print(msg)
                        results.append(msg)
                        continue

                # 正常的字符串原子替换
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

                # 创建子 MOC 导航页面
                res = create_page(
                    file_name=moc_path,
                    title=moc_title,
                    tags=["#MOC", "#导航地图"],
                    abstract=f"关于 {old_str.replace('#', '').strip()} 领域的知识汇聚与导航地图。",
                    content=moc_content
                )
                print(f"  -> 🌟 [细胞裂变] 成功创建子地图: {safe_title}.md")

                # 精细截断并更新主 index.md
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

                    # 如果导航目标文件本身不存在，执行初始化
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

                    # 安全追加，防止重复链接产生
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