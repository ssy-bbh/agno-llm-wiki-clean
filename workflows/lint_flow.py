"""
lint_flow.py — 审查流水线
定期驱动大模型扫描整个 wiki 目录，清理死链或孤立页面。
"""
from pathlib import Path
import re

from agno import Workflow

DATA_WIKI = Path(__file__).parent.parent / "data" / "wiki"

# 全局寻址文件（lint 前后都需读取）
INDEX_FILE = DATA_WIKI / "index.md"
LOG_FILE = DATA_WIKI / "log.md"


class LintFlow(Workflow):
    """
    审查流水线（Lint Flow）。

    定期执行以下步骤：
    1. 扫描 data/wiki/ 下所有 .md 文件
    2. 提取所有 [[target]] 双向链接引用
    3. 检查被引用页面是否真实存在
    4. 汇总孤立页面（无任何引用）写入 log.md
    5. 在 index.md 的孤立页面节更新清单
    """

    name: str = "wiki_lint_flow"
    description: str = "扫描 Wiki 目录，清理死链和孤立页面"

    def run(self, verbose: bool = True) -> dict:
        all_files = self._collect_md_files()
        all_links = self._extract_all_links(all_files)

        dead_links = []
        for link_target in all_links:
            # 解析 [[target]] → 目标文件名为 target.md
            target_file = (DATA_WIKI / "concepts" / f"{link_target}.md").resolve()
            if not target_file.exists():
                # 尝试 entities/ 目录
                target_file = (DATA_WIKI / "entities" / f"{link_target}.md").resolve()
                if not target_file.exists():
                    dead_links.append(link_target)

        orphans = self._find_orphans(all_files, all_links)
        index = self._read_index()

        # 更新孤立页面清单
        log_entry = self._build_log_entry(dead_links, orphans)
        self._append_log(log_entry)

        if verbose:
            print(f"[LintFlow] 扫描 {len(all_files)} 个文件")
            print(f"[LintFlow] 死链: {dead_links}")
            print(f"[LintFlow] 孤立页面: {orphans}")

        return {
            "total_files": len(all_files),
            "dead_links": dead_links,
            "orphans": orphans,
            "log_entry": log_entry,
        }

    # ── 内部工具 ───────────────────────────────────────────────

    def _collect_md_files(self) -> list[Path]:
        files = []
        for subdir in ("concepts", "entities"):
            d = DATA_WIKI / subdir
            if d.is_dir():
                files.extend(d.glob("*.md"))
        if INDEX_FILE.exists():
            files.append(INDEX_FILE)
        return files

    def _extract_all_links(self, files: list[Path]) -> set[str]:
        links = set()
        for f in files:
            text = f.read_text(encoding="utf-8")
            # 匹配 [[target]] 或 [[target|display]]
            found = re.findall(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]", text)
            links.update(found)
        return links

    def _find_orphans(self, files: list[Path], all_links: set[str]) -> list[str]:
        """孤立页面：文件存在但从未被任何 [[]] 引用"""
        created_links = {f.stem for f in files if f.stem not in ("index", "log")}
        orphans = [f for f in created_links if f not in all_links]
        return orphans

    def _read_index(self) -> str:
        if INDEX_FILE.exists():
            return INDEX_FILE.read_text(encoding="utf-8")
        return ""

    def _build_log_entry(self, dead_links: list, orphans: list) -> str:
        from datetime import datetime
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"- **{ts}** | LINT | "
        if dead_links:
            entry += f"死链: {', '.join(dead_links)}"
        if orphans:
            entry += f"孤立页面: {', '.join(orphans)}"
        if not dead_links and not orphans:
            entry += "✅ 未发现问题"
        return entry

    def _append_log(self, entry: str) -> None:
        if not LOG_FILE.exists():
            LOG_FILE.write_text("# LLM Wiki — 审计日志\n\n", encoding="utf-8")
        LOG_FILE.write_text(
            LOG_FILE.read_text(encoding="utf-8") + entry + "\n",
            encoding="utf-8",
        )
