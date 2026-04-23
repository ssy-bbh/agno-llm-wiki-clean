"""
edit_tools.py — 局部精准编辑工具
基于 str_replace 实现精密替换，防止全量覆写导致 Markdown 格式错乱。
每次操作均为原子性：读取 → 定位 old_str → 替换为 new_str → 一次性写回。
"""
import re
from pathlib import Path
from typing import Optional

WIKI_ROOT = Path(__file__).parent.parent / "data" / "wiki"


def _resolve(path: str) -> Path:
    """将相对路径安全解析到 WIKI_ROOT 内。"""
    p = (WIKI_ROOT / path.lstrip("/")).resolve()
    if not str(p).startswith(str(WIKI_ROOT.resolve())):
        raise PermissionError(f"路径越界: {path}")
    return p


def str_replace(
    file_path: str,
    old_str: str,
    new_str: str,
    search_scope: Optional[str] = None,
) -> str:
    """
    在指定文件中，将第一个匹配的 old_str 替换为 new_str。

    Args:
        file_path:  目标文件路径（相对于 WIKI_ROOT）
        old_str:    要替换的原文（必须精确匹配，空白符完全一致）
        new_str:    替换后的新内容
        search_scope: 可选，限制搜索范围的正则表达式区间
                     例如 r"(?s)## Abstract.*?(?=##|$)" 只在 Abstract 节内替换

    Returns:
        操作摘要："已替换 X 处，共 Y 个字符"
    """
    path = _resolve(file_path)
    content = path.read_text(encoding="utf-8")

    if search_scope:
        match = re.search(search_scope, content)
        if not match:
            raise ValueError(f"未在 {file_path} 中找到搜索区间: {search_scope}")
        scope = match.group()
        if old_str not in scope:
            raise ValueError(
                f"在搜索区间内未找到 old_str。\n"
                f"区间内容: {scope[:200]}"
            )
        new_scope = scope.replace(old_str, new_str, 1)
        new_content = content.replace(scope, new_scope, 1)
    else:
        if old_str not in content:
            raise ValueError(
                f"未在 {file_path} 中找到 old_str。\n"
                f"old_str: {repr(old_str[:100])}"
            )
        new_content = content.replace(old_str, new_str, 1)

    path.write_text(new_content, encoding="utf-8")
    return (
        f"✅ 已在 {file_path} 中完成替换\n"
        f"   旧: {repr(old_str[:80])}...\n"
        f"   新: {repr(new_str[:80])}..."
    )


def append_to_log(entry: str) -> str:
    """
    向 log.md 追加只读追加的审计日志条目。
    格式: YYYY-MM-DD HH:MM | action | file | detail
    """
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"- **{timestamp}** | {entry}\n"
    path = _resolve("log.md")
    path.write_text(
        path.read_text(encoding="utf-8") + line,
        encoding="utf-8",
    )
    return f"✅ 审计日志已追加: {entry}"


def create_page(
    file_name: str,
    template: str,
    title: str,
    tags: list[str],
    abstract: str = "",
) -> str:
    """
    在 concepts/ 或 entities/ 下创建新的 Markdown 页面。

    Args:
        file_name:  文件名（不含路径，如 "attention-mechanism.md"）
        template:   "concept" 或 "entity"
        title:      页面标题
        tags:       标签列表，如 ["#transformer", "#nlp"]
        abstract:   简短摘要（可选）
    """
    path = _resolve(f"concepts/{file_name}")
    if path.exists():
        raise FileExistsError(f"页面已存在: {path}")

    tag_line = " ".join(tags)
    date = __import__("datetime").datetime.now().strftime("%Y-%m-%d")

    body = f"""# {title}

> **Tags:** {tag_line}
> **Created:** {date}
> **Updated:** {date}

## Abstract

{abstract or "（暂无摘要）"}

## Key Concepts

-

## Details


## Related

-

## References

-
"""
    path.write_text(body, encoding="utf-8")
    append_to_log(f"CREATE | {path.name} | 新建 {template} 页面")
    return f"✅ 已创建: {path.name}"


def get_or_create_index() -> str:
    """确保 index.md 存在，不存在则创建空模板。"""
    path = _resolve("index.md")
    if path.exists():
        return path.read_text(encoding="utf-8")
    body = """# LLM Wiki — 全局导航地图

> ⚠️ 本文件是 LLM Wiki 的核心寻址文件，Agent 每次查询和写入前必须先阅读此文件。

## 最近更新

（暂无）

## 顶层分类

-

## 核心概念（Concepts）

-

## 核心实体（Entities）

-

## 孤立页面

（无）
"""
    path.write_text(body, encoding="utf-8")
    return body
