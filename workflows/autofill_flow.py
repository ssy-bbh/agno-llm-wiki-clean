"""
autofill_flow.py — 幽灵节点实例化引擎 (知识黑洞自动填补)
"""
import os
import re
from pathlib import Path
from collections import Counter

from agents.wiki_editor import WikiEditor
from agents.wiki_writer import WikiWriter
from tools.edit_tools import _resolve


class AutoFillFlow:
    def __init__(self, threshold: int = 2):
        """
        :param threshold: 触发自动填补的最小入度（默认被提及 2 次及以上就触发）
        """
        self.threshold = threshold
        self.writer = WikiWriter()

    def _normalize_name(self, text: str) -> str:
        if not text: return ""
        return re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', text).lower()

    def run(self):
        kb_name = os.environ.get("ACTIVE_KB", "default")
        print("\n" + "=" * 60)
        print(f"🕳️ [AutoFill Flow] 启动知识黑洞探测器 | 目标沙箱: {kb_name}")

        concepts_dir = Path("../data/wiki") / kb_name / "concepts"
        if not concepts_dir.exists():
            print("❌ concepts 目录不存在，图谱为空，无法探测。")
            return

        # ==========================================
        # 1. 扫描与入度统计
        # ==========================================
        link_counter = Counter()
        backlinks_context = {}  # 记录谁引用了它，用于给大模型提供溯源上下文

        print("📡 正在全盘扫描物理文件并提取双向链接...")
        for file_path in concepts_dir.glob("*.md"):
            content = file_path.read_text(encoding="utf-8")

            # 提取所有 [[xxx]] 或 [[xxx|yyy]] 格式的链接
            links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)

            for link in links:
                clean_link = link.strip()
                if not clean_link: continue

                link_counter[clean_link] += 1

                if clean_link not in backlinks_context:
                    backlinks_context[clean_link] = []
                # 记录来源文件的名字
                if file_path.stem not in backlinks_context[clean_link]:
                    backlinks_context[clean_link].append(file_path.stem)

        # ==========================================
        # 2. 过滤、锁定与【偷天换日】底层链接修复
        # ==========================================
        target_ghosts = []
        existing_files = list(concepts_dir.glob("*.md"))

        def _get_real_target_if_exists(ghost_name: str, files: list) -> str:
            """终极防撞雷达：基于括号解构的别名集合交集法，0误杀！"""
            import re

            def _get_aliases(text: str) -> set:
                aliases = set()
                # 1. 放入整体干净名称 (去掉横线空格等干扰符)
                clean_text = text.lower().replace("-", "").replace("_", "").replace(" ", "")
                if clean_text:
                    aliases.add(clean_text)

                # 2. 如果符合 "A (B)" 或 "A（B）" 格式，安全拆解出 A 和 B 作为独立别名
                match = re.match(r'^(.*?)\s*[\(（](.*?)[\)）]', text)
                if match:
                    part1 = match.group(1).lower().replace("-", "").replace("_", "").replace(" ", "")
                    part2 = match.group(2).lower().replace("-", "").replace("_", "").replace(" ", "")
                    if part1: aliases.add(part1)
                    if part2: aliases.add(part2)

                return aliases

            ghost_aliases = _get_aliases(ghost_name)

            for ex_file in files:
                ex_aliases = _get_aliases(ex_file.stem)

                # 🎯 核心魔法：集合求交集。只要有一个别名完全对上，就是同一个概念！
                if ghost_aliases & ex_aliases:
                    return ex_file.stem

            return ""

        print("\n" + "=" * 60)
        print("🛠️ [自愈系统] 正在进行假空节点清洗与底层链接重定向...")

        for link, count in link_counter.items():
            real_target = _get_real_target_if_exists(link, existing_files)

            if real_target:
                if link != real_target:
                    print(f"  -> 🔀 [偷天换日] 发现异名假空节点 [{link}] -> 真实归宿 [{real_target}]")
                    for source_file in backlinks_context[link]:
                        source_path = concepts_dir / f"{source_file}.md"
                        if source_path.exists():
                            content = source_path.read_text(encoding="utf-8")
                            pattern = re.compile(rf'\[\[{re.escape(link)}(?:\|([^\]]+))?\]\]')
                            new_content = pattern.sub(lambda m: f"[[{real_target}|{m.group(1) or link}]]",
                                                      content)

                            if new_content != content:
                                source_path.write_text(new_content, encoding="utf-8")
                                print(f"    -> ✅ 成功重定向文件底层的幽灵指针: {source_file}.md")
            else:
                # 🎯 这里是纯正的真空节点！大模型没写过的处女地！
                if count >= self.threshold:
                    target_ghosts.append((link, count))

        # 按入度从高到低排序
        target_ghosts.sort(key=lambda x: x[1], reverse=True)

        # 💡 把打印真空节点的逻辑独立出来，让你一眼看到它们！
        if not target_ghosts:
            print("\n✅ 图谱极其健康，没有发现达到阈值的真空知识黑洞。")
        else:
            print(f"\n🎯 警报！发现 {len(target_ghosts)} 个高频真空节点 (入度 >= {self.threshold})：")
            for node, count in target_ghosts:
                sources = ", ".join(backlinks_context[node][:3])
                more = "..." if len(backlinks_context[node]) > 3 else ""
                print(f"  - [{node}] (入度: {count} | 来源: {sources}{more})")
        # ==========================================
        # 3. 逐个召唤主编进行物理填补
        # ==========================================
        print("\n" + "=" * 60)
        print("🪄 开始自动合成节点...")

        for node, count in target_ghosts:
            print(f"\n✨ [实例化] 正在合成空节点: [{node}]")

            # 💡 核心魔法：组装溯源上下文
            # 把引用了这个概念的原文开头拿出来，喂给大模型，防止它胡编乱造
            source_docs_str = ""
            for source_file in backlinks_context[node][:3]:
                source_path = _resolve(f"concepts/{source_file}.md")
                if source_path.exists():
                    snippet = source_path.read_text(encoding='utf-8')[:600]  # 取前600字
                    source_docs_str += f"\n=== {source_file} (提及了该概念) ===\n{snippet}...\n"

            prompt_text = (
                f"你是一个知识图谱修复专家。目前系统内有一个核心概念【{node}】被多次引用，"
                f"但其独立条目缺失。请基于你的通用知识，以及下面提供的一些本地关联文档的上下文，"
                f"直接生成关于【{node}】的详细百科解释。\n\n"
                f"关联上下文参考：\n{source_docs_str}"
            )

            try:
                # 每次重新实例化主编，确保脑子干净
                fresh_editor = WikiEditor()

                # 欺骗大模型，把它当作普通的合并任务
                report = fresh_editor.merge(
                    raw_text=prompt_text,
                    analyst_summary=f"这是一个高频核心实体，必须创建一个全新的详细词条：{node}",
                    existing_context=f"=== concepts/{node}.md ===\n(全新概念，待你创建)\n"
                )

                if report and report.get("actions"):
                    self.writer.execute(report)
                else:
                    print(f"  -> ⏭️ 主编拒绝生成: [{node}]")
            except Exception as e:
                print(f"  -> ❌ 填补 [{node}] 时发生致命错误: {e}")

        print("\n" + "=" * 60)
        print("✅ [AutoFill Flow] 幽灵节点全部实例化完毕，图谱经脉已打通！")


if __name__ == "__main__":
    import sys
    from pathlib import Path

    wiki_dir = Path("../data/wiki")

    if not wiki_dir.exists():
        print(f"❌ 找不到 {wiki_dir} 目录，当前没有任何知识库！")
        sys.exit(0)

    # 扫描所有的子文件夹（每一个子文件夹就是一个独立的知识库）
    kbs = [p for p in wiki_dir.iterdir() if p.is_dir()]

    if not kbs:
        print(f"📭 {wiki_dir} 目录下空空如也，请先运行摄入流生成知识图谱。")
        sys.exit(0)

    print("\n" + "=" * 50)
    print("🕳️ 欢迎使用 幽灵节点自动实例化引擎 (黑洞填补)")
    print("=" * 50)
    print("请选择你要扫描并修补的知识库：\n")

    for i, kb in enumerate(kbs, 1):
        print(f"  [{i}] 📚 {kb.name}")
    print("\n" + "=" * 50)

    try:
        choice = input("👉 请输入对应编号 (按 Ctrl+C 退出): ").strip()
        choice_idx = int(choice) - 1
        if choice_idx < 0 or choice_idx >= len(kbs):
            raise ValueError
    except (ValueError, IndexError):
        print("❌ 输入无效，请输入正确的数字编号。")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 已取消操作。")
        sys.exit(0)

    # 获取用户选择的真实知识库名称
    selected_kb = kbs[choice_idx].name

    # 注入环境变量，让底层的 _resolve 函数知道该去哪个目录干活
    os.environ["ACTIVE_KB"] = selected_kb
    os.environ["ACTIVE_SUBDIR"] = ""

    print(f"\n🚀 锁定目标沙箱: [{selected_kb}]，准备启动侦测...")

    # 触发阈值可以自己调，这里设定被引用 2 次及以上就触发填补
    flow = AutoFillFlow(threshold=2)
    flow.run()