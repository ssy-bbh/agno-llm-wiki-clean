"""
edit_tools.py — 局部精准编辑工具 (纯手写安全版)
"""
from pathlib import Path

# 锁定操作根目录，绝对不准越界
WIKI_ROOT = Path(__file__).parent.parent / "data" / "wiki"


def _resolve(path: str) -> Path:
    """安全寻址：确保所有文件读写都被死死圈在 data/wiki/ 目录下"""
    p = (WIKI_ROOT / path.lstrip("/")).resolve()
    if not str(p).startswith(str(WIKI_ROOT.resolve())):
        raise PermissionError(f"🚨 安全拦截：试图越界访问目录 -> {path}")
    return p


def create_page(file_name: str, title: str, tags: list[str], abstract: str) -> str:
    """严格按照 schema 模板创建新页面"""
    path = _resolve(file_name)

    # 确保父目录(如 concepts/)存在
    path.parent.mkdir(parents=True, exist_ok=True)

    # 防覆盖锁：如果文件已经存在，直接拒绝覆写
    if path.exists():
        return f"⚠️ 警告：页面已存在，拒绝覆写 ({file_name})"

    tag_str = " ".join(tags)
    import datetime
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    # 强制套用标准模板
    body = f"""# {title}

> **Tags:** {tag_str}
> **Created:** {date_str}

## Abstract
{abstract}

## Details
（等待后续扩展）

## Related
- 

## References
- 
"""
    path.write_text(body, encoding="utf-8")
    return f"✅ 成功创建页面：{path.name}"