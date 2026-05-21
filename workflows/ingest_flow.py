import json
import sys
import os
import re
import threading
from pathlib import Path
from collections import defaultdict
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.wiki_analyst import WikiAnalyst
from agents.wiki_editor import WikiEditor
from agents.wiki_writer import WikiWriter
from tools.document_parser import extract_text, chunk_text
from tools.edit_tools import _resolve  # 使用原生路由


class IngestFlow:
    """
    知识摄入流水线 (终极形态：Map-Reduce 降维打击版)
    完全摒弃锁机制，彻底解决并发竞态与大模型 Token 冗余浪费。
    """

    def __init__(self):
        self.analyst = WikiAnalyst()
        self.editor = WikiEditor()
        self.writer = WikiWriter()

    def _normalize_name(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', text).lower()

    def _find_existing_file(self, concept: str) -> Path:
        """同义词嗅探器：使用纯粹的原生 Path 在当前 concepts 目录下寻找"""
        # 💡 移除了 _resolve()
        concepts_dir = Path("concepts")
        if not concepts_dir.exists():
            return None

        norm_c = self._normalize_name(concept)
        if not norm_c:
            return None

        for f in concepts_dir.glob("*.md"):
            norm_f = self._normalize_name(f.stem)

            # 1. 核心去重：完全一致
            if norm_c == norm_f:
                return f
            # 2. 同义词判定
            if len(norm_c) > 2 and len(norm_f) > 2:
                if norm_c in norm_f or norm_f in norm_c:
                    return f

        return None

    def _fetch_local_context(self, concepts: list) -> str:
        """档案管理员：提取上下文并告诉主编真实的文件名"""
        context_str = "\n"

        # 💡 移除了 _resolve()
        index_path = Path("index.md")
        if index_path.exists():
            context_str += f"=== index.md (导航地图) ===\n{index_path.read_text(encoding='utf-8')}\n\n"
        else:
            context_str += "=== index.md (导航地图) ===\n(文件不存在)\n\n"

        for concept in concepts:
            real_file = self._find_existing_file(concept)

            if real_file:
                content = real_file.read_text(encoding="utf-8")
                # 已经是原生 Path，name 属性就是文件名
                rel_path = f"concepts/{real_file.name}"
                context_str += f"=== {rel_path} (本地已存在) ===\n{content}\n\n"
            else:
                safe_name = concept.replace("/", "_").replace("\\", "_").replace(":", "_").replace("?", "_")
                context_str += f"=== concepts/{safe_name}.md ===\n(全新概念)\n\n"

        return context_str

    def _map_extract(self, chunk, chunk_id):
        """Map 阶段的核心逻辑：只提取，不写盘，无锁狂奔"""
        try:
            print(f"  [Map 线程 {chunk_id}] 🕵️‍♂️ 提取中...")
            analysis_result = self.analyst.analyze(chunk)
            if not analysis_result.get("new_concepts"):
                return chunk_id, chunk, None, "无核心概念"
            return chunk_id, chunk, analysis_result, "成功"
        except Exception as e:
            return chunk_id, chunk, None, f"报错: {str(e)}"

    def run(self, input_source: str):
        print("\n" + "=" * 60)
        print("🚀 [IngestFlow] 启动终极 Map-Reduce 知识摄入引擎...")

        path = Path(input_source)
        if path.exists() and path.is_file():
            print(f"📄 目标文件：{path.name}")
            raw_text = extract_text(str(path))
            chunks = chunk_text(raw_text, chunk_size=1500, overlap=200)
            print(f"✂️ 切分为 {len(chunks)} 个知识块。")
        else:
            chunks = [input_source]

        # ==========================================
        # 🟢 PHASE 1: MAP (无锁绝对并发)
        # ==========================================
        print("\n" + "=" * 60)
        print("⚡ [Phase 1: MAP] 启动侦察兵并发提取 (释放全部线程)...")

        map_results = []
        with ThreadPoolExecutor(max_workers=12) as executor:
            futures = {executor.submit(self._map_extract, chunk, i + 1): i for i, chunk in enumerate(chunks)}
            for future in as_completed(futures):
                cid, chunk_text_val, res, status = future.result()
                if res:
                    map_results.append((chunk_text_val, res))
                    print(f"  -> ✅ 线程 {cid} 提取完毕: {res.get('new_concepts')}")

                # ==========================================
                # 🟡 PHASE 2: SHUFFLE (内存级同义词聚类)
                # ==========================================
                print("\n" + "=" * 60)
                print("🔀 [Phase 2: SHUFFLE] 正在将碎片知识按概念重新洗牌聚类 (启动双语解构引擎)...")

                import re

                concept_payloads = {}
                for chunk_text_val, res in map_results:
                    concepts = res.get("new_concepts", [])
                    summary = res.get("summary", "")

                    for raw_c in concepts:
                        # 💡 1. 核心魔法：用正则把 "Self-Attention (自注意力)" 拆成两半
                        # match.group(1) 是英文，match.group(2) 是中文
                        match = re.match(r'^(.*?)\s*[\(（](.*?)[\)）]', raw_c)

                        if match:
                            en_key = match.group(1).strip()
                            zh_alias = match.group(2).strip()
                            full_display = f"{en_key} ({zh_alias})"  # 统一格式化为完美双语
                        else:
                            # 如果大模型偶尔没遵守规则，兜底处理
                            en_key = raw_c.strip()
                            zh_alias = ""
                            full_display = en_key

                        # 💡 2. 物理拦截：基于拆解出的英文进行长度过滤
                        if len(en_key.split()) > 4 or len(en_key) > 25:
                            continue

                        # 💡 3. 归一化：我们只拿【英文部分】去计算主键！这彻底解决了翻译不一致导致的分裂！
                        norm_c = self._normalize_name(en_key)
                        if not norm_c or len(norm_c) < 2:
                            continue

                        if norm_c not in concept_payloads:
                            concept_payloads[norm_c] = {
                                "primary_key": en_key,  # 例如: "Self-Attention" (用于底层比对)
                                "display_name": full_display,  # 例如: "Self-Attention (自注意力)" (给主编看)
                                "aliases": set(),  # 收集所有的中文翻译变体
                                "texts": [],
                                "summaries": []
                            }

                        if zh_alias:
                            concept_payloads[norm_c]["aliases"].add(zh_alias)

                        concept_payloads[norm_c]["texts"].append(chunk_text_val)
                        concept_payloads[norm_c]["summaries"].append(summary)

        # ==========================================
        # 🔴 PHASE 3: REDUCE (按概念逐个融合)
        # ==========================================
        print("\n" + "=" * 60)
        total_concepts = len(concept_payloads)
        print(f"🧠 [Phase 3: REDUCE] 惊人降维！发现 {total_concepts} 个独立核心概念。")
        print("主编接手，开始统一排版与落盘 (彻底告别死锁)...")

        # 串行合并，完全没有并发写盘冲突！主编只需为每个概念写1次文件！
        for i, (norm_c, payload) in enumerate(concept_payloads.items(), 1):
            display_name = payload["display_name"]  # 这里主编看到的就是 "Self-Attention (自注意力)" 了！
            print(f"\n" + "-" * 50)
            print(f"🔄 [融合 {i}/{total_concepts}] 目标概念: [{display_name}]")

            # 将多块文本拼装
            combined_text = "\n\n... (接上文补充资料) ...\n\n".join(payload["texts"])
            combined_summary = "\n".join(payload["summaries"])

            existing_context = self._fetch_local_context([display_name])

            try:
                report = self.editor.merge(
                    raw_text=combined_text,
                    analyst_summary=combined_summary,
                    existing_context=existing_context
                )

                if report and report.get("actions"):
                    self.writer.execute(report)
                else:
                    print(f"  -> ⏭️ 主编裁定: [{display_name}] 无实质增量信息，跳过写盘。")
            except Exception as e:
                print(f"  -> ❌ 合并 [{display_name}] 时发生致命错误: {e}")

        print("\n" + "=" * 60)
        print("✅ [IngestFlow] 终极降维摄入完毕，知识图谱完美生长！")
        print("=" * 60)


if __name__ == "__main__":
    raw_dir = Path("data/raw")

    if not raw_dir.exists():
        raw_dir.mkdir(parents=True, exist_ok=True)
        print(f"⚠️ 找不到 {raw_dir} 目录，已为您自动创建。请先将数据放入该目录！")
        sys.exit(0)

    items = [p for p in raw_dir.iterdir() if p.is_dir() or p.suffix.lower() == '.pdf']

    if not items:
        print(f"📭 {raw_dir} 目录下空空如也，请先放入包含论文或文档的文件夹。")
        sys.exit(0)

    print("\n" + "=" * 50)
    print("🤖 欢迎使用 LLM-Wiki 自动化摄入系统")
    print("=" * 50)
    print("请选择要处理的知识源：\n")

    for i, item in enumerate(items, 1):
        icon = "📁" if item.is_dir() else "📄"
        print(f"  [{i}] {icon} {item.name}")
    print("\n" + "=" * 50)

    try:
        choice = input("👉 请输入对应编号 (按 Ctrl+C 退出): ").strip()
        choice_idx = int(choice) - 1
        if choice_idx < 0 or choice_idx >= len(items):
            raise ValueError
    except (ValueError, IndexError):
        print("❌ 输入无效，请输入正确的数字编号。")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 已取消操作。")
        sys.exit(0)

    input_target = items[choice_idx]
    kb_name = input_target.stem

    os.environ["ACTIVE_KB"] = kb_name
    print(f"\n🌐 [系统路由] 自动提取并激活知识隔离区: {kb_name}")

    flow = IngestFlow()

    if input_target.is_file():
        os.environ["ACTIVE_SUBDIR"] = ""
        os.environ["ACTIVE_DOC_NAME"] = input_target.stem
        flow.run(str(input_target))

    elif input_target.is_dir():
        files = list(input_target.rglob("*.pdf"))
        print(f"📂 开始深度扫描 [{input_target.name}]，共发现 {len(files)} 个文档。")

        for idx, file_path in enumerate(files, 1):
            if file_path.parent == input_target:
                rel_dir = ""
            else:
                rel_dir = str(file_path.parent.relative_to(input_target))

            os.environ["ACTIVE_SUBDIR"] = rel_dir
            os.environ["ACTIVE_DOC_NAME"] = file_path.stem

            print("\n" + "-" * 50)
            print(f"🚀 [批量进度 {idx}/{len(files)}] 正在解析: {file_path.name}")
            print(f"📁 知识流向: 正在将数据注入至当前激活的底层沙箱环境...")

            flow.run(str(file_path))