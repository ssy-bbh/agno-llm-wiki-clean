"""
edit_tools.py — 局部精准编辑工具 (线程安全·用户隔离版)
"""
import os
import threading
from pathlib import Path

# 锁定操作根目录，绝对不准越界
WIKI_ROOT = Path(__file__).parent.parent / "data" / "wiki"

# ═══════════════════════════════════════════════════════
# 🧵 线程安全上下文（替代 os.environ，解决并发竞态）
# ═══════════════════════════════════════════════════════
_ctx = threading.local()


def set_context(user_id: str = "", kb_name: str = "default", sub_dir: str = "", doc_name: str = ""):
    """设置当前线程的路由上下文（线程安全，不影响其他线程）"""
    _ctx.user_id = user_id
    _ctx.kb_name = kb_name
    _ctx.sub_dir = sub_dir
    _ctx.doc_name = doc_name


def get_context() -> dict:
    """获取当前线程的路由上下文"""
    return {
        "user_id": getattr(_ctx, "user_id", ""),
        "kb_name": getattr(_ctx, "kb_name", "default"),
        "sub_dir": getattr(_ctx, "sub_dir", ""),
        "doc_name": getattr(_ctx, "doc_name", ""),
    }


def _resolve(file_name: str) -> Path:
    """以父文件夹（分类）为中心的统筹路由，支持用户级隔离"""
    ctx = get_context()
    kb_name = ctx["kb_name"]
    sub_dir = ctx["sub_dir"]
    user_id = ctx["user_id"]

    # 用户隔离：data/wiki/{user_id}/{kb_name}/{sub_dir}
    if user_id:
        base_dir = Path(__file__).resolve().parent.parent / "data" / "wiki" / user_id / kb_name / sub_dir
    else:
        base_dir = Path(__file__).resolve().parent.parent / "data" / "wiki" / kb_name / sub_dir

    # 2. 智能路由
    if Path(file_name).name.lower() == "index.md":
        # 强制把 index.md 放在父文件夹的根目录，作为唯一总索引
        final_path = base_dir / "index.md"
    else:
        # 大模型输出的 concepts/xxx.md 或 datasets/xxx.md 直接拼接在父文件夹后面
        final_path = base_dir / file_name

    # 3. 自动创建父级目录（比如自动建好 concepts/）
    final_path.parent.mkdir(parents=True, exist_ok=True)

    return final_path


# 💡 注意参数里多了 content
def create_page(file_name: str, title: str, tags: list[str], abstract: str, content: str = "") -> str:
    """严格按照 schema 模板创建新页面，包含模糊去重机制"""
    path = _resolve(file_name)
    path.parent.mkdir(parents=True, exist_ok=True)

    # 1. 物理级模糊去重锁 (保持不变)
    clean_new_name = path.stem.lower().replace("-", "").replace("_", "").replace(" ", "")
    for existing_file in path.parent.glob("*.md"):
        clean_existing = existing_file.stem.lower().replace("-", "").replace("_", "").replace(" ", "")
        if clean_new_name == clean_existing:
            return f"⚠️ 拦截重复：检测到异名同义词 ({existing_file.name} 已存在)，规避新建：{file_name}"

    if path.exists():
        return f"⚠️ 警告：页面已存在，拒绝覆写 ({file_name})"

    # 💡 2. 核心修复：解决换行符明文显示的 Bug
    abstract = abstract.replace("\\n", "\n")
    content = content.replace("\\n", "\n")

    # 3. 终极 Tags 脏数据清洗 (保持不变)
    clean_tags = []
    if tags:
        if isinstance(tags, str):
            cleaned = tags.replace("[", "").replace("]", "").replace("'", "").replace('"', "")
            clean_tags = [t.strip() for t in cleaned.split(",") if t.strip()]
        elif isinstance(tags, list):
            for t in tags:
                t_str = str(t).replace("[", "").replace("]", "").replace("'", "").replace('"', "").strip()
                if t_str:
                    clean_tags.append(t_str)
    tag_str = " ".join(clean_tags)

    import datetime
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    # 4. 动态注入正文
    details_text = content if content else "（等待后续扩展）"

    # 强制套用标准模板
    body = f"""# {title}

> **Tags:** {tag_str}
> **Created:** {date_str}

## Abstract
{abstract}

## Details
{details_text}

## Related
- 

## References
- 
"""
    path.write_text(body, encoding="utf-8")
    return f"✅ 成功创建页面：{path.name}"


def str_replace(file_name: str, old_str: str, new_str: str) -> str:
    """极其精密的局部替换工具 (带空格宽容 + 活路径路由)"""

    # 💡 核心修复：必须用 _resolve 找回动态活路径！
    path = _resolve(file_name)

    if not path.exists():
        return f"❌ 错误：底层工具找不到文件 ({path})"

    content = path.read_text(encoding="utf-8")

    # 1. 尝试绝对精确匹配
    if old_str in content:
        path.write_text(content.replace(old_str, new_str, 1), encoding="utf-8")
        return f"✅ 成功修改文件：{path.name}"

    # 2. 尝试宽容匹配 (去掉大模型首尾乱加的换行和空格)
    old_str_clean = old_str.strip()
    if old_str_clean and old_str_clean in content:
        path.write_text(content.replace(old_str_clean, new_str, 1), encoding="utf-8")
        return f"✅ 成功修改文件(启用宽容匹配)：{path.name}"

    return f"❌ 找不到旧文本，大模型可能产生了格式幻觉！\n寻找的: {repr(old_str)}"