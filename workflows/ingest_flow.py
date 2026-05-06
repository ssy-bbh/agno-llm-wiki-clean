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
    知识摄入流水线 (多脑协作 · 同义词归一 · 细粒度锁并发版)
    """

    def __init__(self):
        self.analyst = WikiAnalyst()
        self.editor = WikiEditor()
        self.writer = WikiWriter()

        # 💡 细粒度锁池：为每一个概念动态分配一把锁，互不干扰
        self.concept_locks = defaultdict(threading.Lock)

    def _normalize_name(self, text: str) -> str:
        """纯净器：移除所有非字母、数字、中文的字符，转小写"""
        if not text:
            return ""
        return re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', text).lower()

    def _find_existing_file(self, concept: str) -> Path:
        """同义词嗅探器：在本地寻找是否已有相似概念的文件"""
        concepts_dir = _resolve("concepts")
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
            # 2. 同义词判定：互相包含且长度大于2（如"注意力机制" 包含 "注意力"）
            if len(norm_c) > 2 and len(norm_f) > 2:
                if norm_c in norm_f or norm_f in norm_c:
                    return f

        return None

    def _fetch_local_context(self, concepts: list) -> str:
        """档案管理员：提取上下文并告诉主编真实的文件名"""
        context_str = "\n"

        index_path = _resolve("index.md")
        if index_path.exists():
            context_str += f"=== index.md (导航地图) ===\n{index_path.read_text(encoding='utf-8')}\n\n"
        else:
            context_str += "=== index.md (导航地图) ===\n(文件不存在)\n\n"

        for concept in concepts:
            real_file = self._find_existing_file(concept)

            if real_file:
                # 💡 如果查到了同义词文件，强制让主编使用这个已存在的名字！
                content = real_file.read_text(encoding="utf-8")
                rel_path = f"concepts/{real_file.name}"
                context_str += f"=== {rel_path} (本地已存在，匹配到概念 [{concept}]) ===\n{content}\n\n"
            else:
                safe_name = concept.replace("/", "_").replace("\\", "_").replace(":", "_").replace("?", "_")
                context_str += f"=== concepts/{safe_name}.md ===\n(全新概念，文件暂不存在)\n\n"

        return context_str

    def process_single_chunk(self, chunk, chunk_id):
        try:
            print(f"  [线程 {chunk_id}] 🕵️‍♂️ 侦察兵开始提取概念...")
            analysis_result = self.analyst.analyze(chunk)
            new_concepts = analysis_result.get("new_concepts", [])
            summary = analysis_result.get("summary", "")

            if not new_concepts:
                return chunk_id, None, "没有提取到核心概念"

            # 💡 锁的死锁防御机制：对概念归一化后排序，按顺序加锁，绝对不会死锁
            normalized_concepts = list(set([self._normalize_name(c) for c in new_concepts if c]))
            normalized_concepts.sort()

            # 💡 启动细粒度并发锁：只有当前 Chunk 涉及的概念才会被锁住！
            with ExitStack() as stack:
                for norm_c in normalized_concepts:
                    stack.enter_context(self.concept_locks[norm_c])

                print(f"  [线程 {chunk_id}] 🔒 已锁定概念 {new_concepts}，档案员查档中...")
                existing_context = self._fetch_local_context(new_concepts)

                print(f"  [线程 {chunk_id}] 🧠 主编接手，开始比对生成修改指令...")
                report = self.editor.merge(
                    raw_text=chunk,
                    analyst_summary=summary,
                    existing_context=existing_context
                )

                if not report.get("actions"):
                    return chunk_id, None, "主编裁定无增量信息，无需修改"

                # 💡 必须在释放锁之前完成物理写盘，保障后续线程读到的是最新数据！
                self.writer.execute(report)

            return chunk_id, report, "成功"
        except Exception as e:
            return chunk_id, None, f"报错: {str(e)}"

    def run(self, input_source: str):
        print("\n" + "=" * 60)
        print("🚀 [IngestFlow] 启动知识摄入流水线 (多脑协作·细粒度并发锁版)...")

        path = Path(input_source)
        if path.exists() and path.is_file():
            print(f"📄 检测到文件：{path.name}")
            raw_text = extract_text(str(path))
            print("💻 [架构路由] 启用滑动窗口切片策略。")
            chunks = chunk_text(raw_text, chunk_size=1500, overlap=200)
            print(f"✂️ 切分为 {len(chunks)} 个知识块 (Chunk Size: 1500)。")
        else:
            print("📝 检测到短文本输入。")
            chunks = [input_source]

        print("=" * 60)
        print("⚡ 启动高稳定并发处理引擎...")

        total_chunks = len(chunks)
        completed_count = 0

        with ThreadPoolExecutor(max_workers=12) as executor:
            futures = {executor.submit(self.process_single_chunk, chunk, i + 1): i for i, chunk in enumerate(chunks)}

            for future in as_completed(futures):
                completed_count += 1
                try:
                    chunk_id, report, status = future.result()
                    if report:
                        print(f"\n✅ [{completed_count}/{total_chunks}] 线程 {chunk_id} 完全落盘闭环！")
                    else:
                        print(f"\n⏭️ [{completed_count}/{total_chunks}] 线程 {chunk_id} 跳过：{status}")
                except Exception as e:
                    print(f"\n❌ [{completed_count}/{total_chunks}] 致命错误: {e}")

        print("\n" + "=" * 60)
        print("✅ [IngestFlow] 极速摄入与融合完毕，完美收工！")
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