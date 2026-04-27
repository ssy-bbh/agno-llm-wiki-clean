import os
import re
from pathlib import Path

# 锁定 Wiki 目录
WIKI_ROOT = Path(__file__).parent.parent / "data" / "wiki"


class LintFlow:
    """
    知识库审查与织网流水线
    负责全局扫描，自动建立反向链接（Backlinks），并清理死链。
    """

    def __init__(self):
        self.link_pattern = re.compile(r'\[\[(.*?)\]\]')

    def run(self):
        print("\n" + "=" * 60)
        print("🕷️ [LintFlow] 启动全局审查与织网流水线...")
        print("=" * 60)

        # 1. 收集所有 Markdown 文件
        all_md_files = list(WIKI_ROOT.rglob("*.md"))
        print(f"📂 共发现 {len(all_md_files)} 个页面。")

        # 记录映射表： target_concept -> set(source_file_names)
        backlinks_map = {}

        # 2. 全局扫描：谁引用了谁？
        print("\n🔍 正在扫描正向链接...")
        for file_path in all_md_files:
            if file_path.name in ["index.md", "log.md"]:
                continue  # 跳过系统文件

            content = file_path.read_text(encoding="utf-8")
            source_name = file_path.stem  # 比如 'yolov8'

            # 找到当前文件里所有的 [[概念]]
            links = self.link_pattern.findall(content)
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

            # 💡 将 [[概念]] 提取出的文本进行“暴力量化”：全小写，去掉所有横杠、下划线、空格
            clean_target = target_concept.lower().replace("-", "").replace("_", "").replace(" ", "")

            for f in all_md_files:
                # 把硬盘上的文件名也做同样的暴力清洗
                clean_filename = f.stem.lower().replace("-", "").replace("_", "").replace(" ", "")
                if clean_target == clean_filename:
                    target_file = f
                    break

            if not target_file:
                dead_links.append(target_concept)
                continue

            # 找到了目标文件，准备追加 Backlinks
            content = target_file.read_text(encoding="utf-8")

            # 构造要注入的反向链接字符串
            backlink_section = "\n## Backlinks\n"
            for src in sources:
                backlink_section += f"- [[{src}]]\n"

            # 如果已经有 Backlinks 节点，先粗暴替换（实际工程中可以用更精细的 AST 解析，这里做简化演示）
            if "## Backlinks" in content:
                # 简单剥离旧的 Backlinks 及之后的内容
                content = content.split("## Backlinks")[0].strip()

            # 追加新的反向链接
            new_content = content + "\n\n" + backlink_section
            target_file.write_text(new_content, encoding="utf-8")
            updated_count += 1

        print(f"✅ 成功更新了 {updated_count} 个页面的反向链接！")

        if dead_links:
            print(f"\n⚠️ 警告：发现 {len(dead_links)} 个【死链】（有人引用了它，但它没有实体页面）:")
            # 只打印前 5 个示意
            print(", ".join(list(dead_links)[:5]) + " ...")

        print("\n" + "=" * 60)
        print("🕸️ [LintFlow] 织网完成，知识图谱已闭环！")
        print("=" * 60)


if __name__ == "__main__":
    flow = LintFlow()
    flow.run()