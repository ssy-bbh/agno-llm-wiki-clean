"""
file_tools.py — 文件读写工具
利用 agno.tools.file.FileTools 的 base_dir 参数，
严格将 Agent 的读写权限圈禁在 data/wiki/ 内。
"""
from agno.tools.file import FileTools as AgnoFileTools
from pathlib import Path

# 写死安全根目录，Agent 无法跳出此边界
WIKI_ROOT = Path(__file__).parent.parent / "data" / "wiki"


class WikiFileTools:
    """封装 Agno FileTools，带有安全隔离的 wiki 文件工具箱"""

    def __init__(self):
        self._tools = AgnoFileTools(base_dir=str(WIKI_ROOT))

    # ── 读取权限（只读 data/wiki/ 及其子目录） ──────────────────

    def read_file(self, file_path: str) -> str:
        """读取指定 Markdown 文件内容。路径必须在 WIKI_ROOT 内，否则拒绝。"""
        self._check_path(file_path)
        return self._tools.read_file(file_path)

    def list_files(self, dir_path: str = ".") -> list[str]:
        """列出指定目录下的所有 .md 文件。"""
        self._check_path(dir_path)
        return self._tools.list_files(dir_path)

    def search_files(self, search_query: str, file_path: str) -> str:
        """在指定文件内搜索关键词。"""
        self._check_path(file_path)
        return self._tools.search_files(search_query, file_path)

    # ── 禁止操作 ────────────────────────────────────────────────

    def write_file(self, file_path: str, content: str) -> str:
        """禁止直接写入！请使用 EditTools.str_replace()"""
        raise PermissionError(
            "禁止直接覆写文件，请使用 EditTools.str_replace() 进行局部精准编辑。"
        )

    def append_to_file(self, file_path: str, content: str) -> str:
        """仅允许追加到 log.md，禁止写入其他文件。"""
        safe = str(WIKI_ROOT / "log.md")
        target = str(WIKI_ROOT / file_path.lstrip("/"))
        if target != safe:
            raise PermissionError(
                f"append_to_file 仅允许 data/wiki/log.md，当前路径: {target}"
            )
        return self._tools.append_to_file(file_path, content)

    # ── 内部 ────────────────────────────────────────────────────

    def _check_path(self, file_path: str) -> None:
        """路径安全校验：禁止目录遍历（../../ 等）"""
        p = (WIKI_ROOT / file_path.lstrip("/")).resolve()
        if not str(p).startswith(str(WIKI_ROOT.resolve())):
            raise PermissionError(
                f"路径越界！{file_path} 不在 {WIKI_ROOT} 内。"
            )
