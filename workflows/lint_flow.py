import os
import re
import sys
from pathlib import Path

# 锁定 Wiki 目录的绝对坐标
WIKI_ROOT = Path(__file__).parent.parent / "data" / "wiki"


class LintFlow:
    """
    知识库审查与织网流水线
    负责单沙箱扫描，自动建立反向链接（Backlinks），并清理死链。
    """

    def __init__(self):
        self.link_pattern = re.compile(r'\[\[(.*?)\]\]')

    def _select_sandbox(self) -> Path:
        """交互式终端菜单：选择要织网的目标沙箱"""
        if not WIKI_ROOT.exists():
            print(f"❌ 根目录不存在: {WIKI_ROOT}")
            sys.exit(1)

        # 扫描 data/wiki 下所有的第一层文件夹作为独立沙箱
        sandboxes = [d for d in WIKI_ROOT.iterdir() if d.is_dir()]

        if not sandboxes:
            print(f"❌ 在 {WIKI_ROOT} 下没有找到任何知识库沙箱。")
            sys.exit(1)

        print("\n" + "=" * 60)
        print("🗄️ 请选择要进行织网的知识库沙箱：")
        print("-" * 60)

        for i, kb in enumerate(sandboxes):
            print(f"  [{i}] {kb.name}")

        print("-" * 60)

        while True:
            choice = input("👉 请输入对应数字并回车 (输入 q 退出): ").strip()
            if choice.lower() == 'q':
                print("👋 已取消织网操作。")
                sys.exit(0)

            if choice.isdigit():
                idx = int(choice)
                if 0 <= idx < len(sandboxes):
                    return sandboxes[idx]

            print("⚠️ 输入无效，请输入正确的数字序号！")

    def run(self):
        # 0. 启动交互菜单，锁定目标沙箱
        target_kb_dir = self._select_sandbox()
        kb_name = target_kb_dir.name

        print("\n" + "=" * 60)
        print(f"🕷️ [LintFlow] 启动审查与织网流水线 | 🎯 锁定沙箱: [{kb_name}]")
        print("=" * 60)

        # 1. 收集当前沙箱下的所有 Markdown 文件
        # 💡 这里改成了 target_kb_dir.rglob，绝对不会越界扫到别的知识库
        all_md_files = list(target_kb_dir.rglob("*.md"))
        print(f"📂 在 [{kb_name}] 中共发现 {len(all_md_files)} 个页面。")

        if not all_md_files:
            print("⚠️ 该沙箱为空，无需织网。")
            return

        # 记录映射表： target_concept -> set(source_file_names)
        backlinks_map = {}

        # 2. 局部扫描：谁引用了谁？
        print("\n🔍 正在扫描正向链接...")
        for file_path in all_md_files:
            if file_path.name in ["index.md", "log.md"]:
                continue  # 跳过系统文件

            content = file_path.read_text(encoding="utf-8")
            source_name = file_path.stem

            # 找到当前文件里所有的 [[概念]] 和 [[别名|显示文本]]
            # 💡 优化了正则，支持带管道符的别名链接提取
            links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)

            for target in links:
                target_clean = target.strip()
                if target_clean not in backlinks_map:
                    backlinks_map[target_clean] = set()
                backlinks_map[target_clean].add(source_name)

        print(f"🕸️ 扫描完毕，发现 {len(backlinks_map)} 个被引用的概念节点。")

        # 3. 自动织网：写回反向链接
        print("\n✍️ 正在自动写入反向链接 (Backlinks)...")
        updated_count = 0
        dead_links = []

        for target_concept, sources in backlinks_map.items():
            target_file = None

            # 暴力量化防撞
            clean_target = target_concept.lower().replace("-", "").replace("_", "").replace(" ", "")

            for f in all_md_files:
                clean_filename = f.stem.lower().replace("-", "").replace("_", "").replace(" ", "")
                if clean_target == clean_filename:
                    target_file = f
                    break

            if not target_file:
                dead_links.append(target_concept)
                continue

            content = target_file.read_text(encoding="utf-8")

            # 构造要注入的反向链接字符串
            backlink_section = "\n## Backlinks\n"
            for src in sources:
                backlink_section += f"- [[{src}]]\n"

            # 简单剥离旧的 Backlinks 及之后的内容
            if "## Backlinks" in content:
                content = content.split("## Backlinks")[0].strip()

            # 追加新的反向链接
            new_content = content + "\n\n" + backlink_section
            target_file.write_text(new_content, encoding="utf-8")
            updated_count += 1

        print(f"✅ 成功更新了 {updated_count} 个页面的反向链接！")

        if dead_links:
            print(f"\n⚠️ 警告：发现 {len(dead_links)} 个【死链】（在当前沙箱中无实体页面）:")
            print(", ".join(list(dead_links)[:5]) + (" ..." if len(dead_links) > 5 else ""))

        print("\n" + "=" * 60)
        print(f"🕸️ [LintFlow] [{kb_name}] 织网完成，局部知识图谱已闭环！")
        print("=" * 60)


if __name__ == "__main__":
    flow = LintFlow()
    flow.run()