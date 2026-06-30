"""
wiki_writer.py — 知识撰稿人 (活路径雷达 + 严格写盘版)
"""
import re
from tools.edit_tools import _resolve, create_page, str_replace, _resolve_key, get_context
from core.storage import get_storage
from core.path_resolver import minio_wiki_prefix, minio_concepts_prefix

class WikiWriter:
    def execute(self, report: dict) -> list[str]:
        print("\n[WikiWriter] 拿到分析报告，开始物理写盘...")
        actions = report.get("actions", [])
        results = []

        # 🔄 循环检测：防止重复执行相同的操作
        seen_actions = set()

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

            # 🔄 循环检测：同文件 + 同操作 + 同内容前100字 = 重复，跳过
            dedup_key = (
                action.get("file", ""),
                act_type,
                (action.get("content", "") or "")[:100],
                (action.get("old_str", "") or "")[:100],
            )
            if dedup_key in seen_actions:
                print(f"  -> 🔄 循环检测：跳过重复操作 [{act_type}] {action.get('file', '?')}")
                continue
            seen_actions.add(dedup_key)

            raw_file = action.get("file", "concepts/untitled.md")
            if not raw_file.startswith("concepts/") and raw_file != "index.md":
                raw_file = f"concepts/{raw_file}"

            # 💡 核心修复 1：使用 _resolve() 计算出最终活路径，雷达扫描必须基于真实路径！
            target_path = _resolve(raw_file)

            if act_type == "create":
                title = (action.get("title") or target_path.stem).strip()
                safe_title = title.replace("/", "_").replace("\\", "_").replace(":", "_").replace("?", "_")

                # 🛡️ 拦截：禁止在 concepts/ 里创建 index.md（那是根目录的导航地图）
                if raw_file.endswith("concepts/index.md") or safe_title.lower() == "index":
                    msg = f"  -> 🚫 拦截非法创建：概念文件不能叫 index.md，已丢弃动作。"
                    print(msg)
                    results.append(msg)
                    continue

                # 重新计算一次最标准的真实路径，防止大模型名字给得不规范
                perfect_raw_file = f"concepts/{safe_title}.md"
                perfect_target_path = _resolve(perfect_raw_file)

                # 🛡️ 物理拦截雷达启动（统一存储接口，消除 MinIO/Local 分支）
                s = get_storage()
                ctx = get_context()
                concepts_prefix = minio_concepts_prefix(ctx["user_id"], ctx["kb_name"])
                found_existing_key = None
                all_concept_keys = s.list_keys(concepts_prefix)
                for _w_k in all_concept_keys:
                    if _w_k.endswith(".md"):
                        _w_stem = _w_k.split("/")[-1].replace(".md", "")
                        if _is_same_concept(_w_stem, title):
                            found_existing_key = _w_k
                            break

                if found_existing_key:
                    _ex_name = found_existing_key.split("/")[-1]
                    print(f"  -> 🛡️ 拦截创建冲突：同义词文件 [{_ex_name}] 已存在，自动转为 [增量追加]...")
                    safe_new_content = action.get("content", "").replace("\\n", "\n")
                    updated_content = s.read_text(found_existing_key) + f"\n\n---\n### 🧠 增量融合视角 ({title})\n{safe_new_content}\n"
                    s.write_text(found_existing_key, updated_content)
                    results.append(f"成功合并至: {_ex_name}")
                    continue

                # 工具层依然接收相对的 perfect_raw_file 即可，里面会再次 _resolve
                res = create_page(perfect_raw_file, title, action.get("tags", []), action.get("abstract", ""), action.get("content", ""))
                print(f"  -> {res}")
                results.append(res)

            elif act_type == "edit":
                s = get_storage()
                ctx = get_context()
                _edit_found = False

                # index.md 在根目录，直接放行
                if raw_file == "index.md":
                    _e_idx_key = _resolve_key("index.md")
                    if s.exists(_e_idx_key):
                        _edit_found = True

                if not _edit_found:
                    concepts_prefix = minio_concepts_prefix(ctx["user_id"], ctx["kb_name"])
                    _e_keys = s.list_keys(concepts_prefix)
                    _e_target_stem = raw_file.replace("concepts/", "").replace(".md", "")
                    for _e_k in _e_keys:
                        if _e_k.endswith(".md"):
                            _e_stem = _e_k.split("/")[-1].replace(".md", "")
                            if _is_same_concept(_e_stem, _e_target_stem):
                                raw_file = f"concepts/{_e_stem}.md"
                                print(f"  -> 🔍 纠错重定向：已自动扭转至 [{_e_stem}.md]")
                                _edit_found = True
                                break

                if not _edit_found:
                    msg = f"  -> ❌ 严格模式拦截：找不到编辑目标 ({raw_file})，已丢弃动作。"
                    print(msg)
                    results.append(msg)
                    continue

                res = str_replace(raw_file, (action.get("old_str") or "").replace("\\n", "\n"), (action.get("content") or "").replace("\\n", "\n"))
                print(f"  -> {res}")
                results.append(res)


            elif act_type == "extract_moc":

                # 1. 兼容大模型输出的多行文本和转义换行符

                old_str = action.get("old_str", "").replace("\\n", "\n")

                moc_title = (action.get("title", "")).strip()

                moc_content = action.get("content", "")

                safe_title = moc_title.replace("/", "_").replace("\\", "_").replace(":", "_").replace("?", "_")

                moc_raw_path = f"concepts/{safe_title}.md"

                # 抽出第一行作为纯文本标题，避免 f-string 解析多行文本报错

                desc_title = old_str.replace('#', '').strip().split('\n')[0] if old_str else moc_title

                res = create_page(moc_raw_path, moc_title, ["#MOC", "#导航地图"],
                                  f"关于 {desc_title} 领域的知识汇聚与导航地图。", moc_content)

                print(f"  -> 🌟 [细胞裂变] 成功创建子地图: {safe_title}.md")

                # 2. 核心：守护上下文的智能折叠算法

                s = get_storage()
                _m_idx_key = _resolve_key("index.md")
                _moc_content = None
                if s.exists(_m_idx_key):
                    _moc_content = s.read_text(_m_idx_key)

                if _moc_content is not None:
                    content = _moc_content

                    if not old_str.strip():
                        continue

                    # 提取雷达锚点：只要命中第一行标题即可

                    first_line = old_str.strip().split('\n')[0]

                    target_anchor = first_line.replace("#", "").strip().lower()

                    lines = content.split('\n')

                    new_lines = []

                    in_target_section = False

                    replaced = False

                    for line in lines:

                        # 锚点命中：当前行是标题，且包含目标文本，开启折叠区间

                        if not in_target_section and line.strip().startswith('#') and target_anchor in line.lower():
                            in_target_section = True

                            new_lines.append(line)  # 保留这个父级标题

                            continue

                        if in_target_section:

                            # 遇到下一个带 # 的标题，关闭折叠区间，恢复正常解析

                            if line.strip().startswith('#'):

                                in_target_section = False

                                new_lines.append(line)


                            # 🎯 核心逻辑：只折叠具体的概念链接！

                            elif (line.strip().startswith('-') or line.strip().startswith(
                                    '*')) and '[[' in line and ']]' in line:

                                # 只要是带有双链的列表项，统统被折叠为 MOC 入口

                                if not replaced:
                                    new_lines.append(f"- 🗂️ [[{moc_title}]]")

                                    replaced = True

                            else:

                                # 🛡️ 守护机制：领域描述、没有链接的说明文字、排版空行，原封不动保留！

                                new_lines.append(line)

                        else:

                            new_lines.append(line)

                    s.write_text(_m_idx_key, '\n'.join(new_lines))

                    print(f"  -> ✂️ [精细截断] index.md 导航地图已优雅折叠至 [[{moc_title}]] (已保留上下文描述)")

            elif act_type == "append_link":
                old_str = action.get("old_str")
                raw_link_to = str(action.get("link_to", ""))

                if old_str and raw_link_to:
                    links = re.findall(r'\[\[.*?\]\]', raw_link_to)
                    if not links:
                        clean_name = raw_link_to.replace("[", "").replace("]", "").replace('"', "").replace("'", "").strip()
                        # 过滤掉 None 字符串（LLM 返回 null 时 str(None) = "None"）
                        if clean_name and clean_name.lower() != "none":
                            links = [f"[[{clean_name}]]"]
                    # 过滤无效链接：去掉 [[None]]、[[index.md]]、[[concepts/]] 等非概念名
                    links = [l for l in links if re.search(r'\[\[(?!None\]\]).+?\]\]', l)
                             and '/' not in l and '.md' not in l]

                    s = get_storage()
                    _al_key = _resolve_key(raw_file)
                    if not s.exists(_al_key):
                        _al_ctx = get_context()
                        _al_folder = _al_ctx["kb_name"] or "全局"
                        s.write_text(_al_key, f"# {_al_folder} 知识导航\n\n{old_str}\n")

                    content = s.read_text(_al_key)
                    if old_str not in content:
                        content += f"\n\n{old_str}\n"
                        s.write_text(_al_key, content)
                        content = s.read_text(_al_key)

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
                        res = str_replace(raw_file, old_str, new_str)
                        print(f"  -> [导航地图更新] 追加 {single_link} 成功")
                        old_str = new_str
                        results.append(res)
            else:
                print(f" -> ⚠️ 暂未实现的操作类型: {act_type}")

        return results
