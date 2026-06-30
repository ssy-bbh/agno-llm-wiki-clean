"""
edit_tools.py — 局部精准编辑工具 (线程安全·用户隔离版)
"""
import os
import threading
from pathlib import Path

from core.storage import get_storage

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

def _resolve_key(file_name: str) -> str:
    """返回 MinIO 对象 Key（对应本地 _resolve 返回的 Path）"""
    ctx = get_context()
    parts = ["wiki"]
    if ctx["user_id"]:
        parts.append(ctx["user_id"])
    parts.append(ctx["kb_name"])
    if ctx["sub_dir"]:
        parts.append(ctx["sub_dir"])
    if Path(file_name).name.lower() == "index.md":
        parts.append("index.md")
    else:
        parts.append(file_name)
    return "/".join(parts)




def _sanitize_filename(file_name: str) -> str:
    """清洗 LLM 生成的脏文件名：保留 concepts/ 前缀，只清洗文件名部分"""
    import re
    name = file_name.strip()

    # 分离目录前缀和文件名
    if "/" in name:
        dir_part = "/".join(name.split("/")[:-1]) + "/"
        base = name.split("/")[-1]
    else:
        dir_part = ""
        base = name

    # 去 markdown 标记 (###, ##, #, -, *)
    base = re.sub(r"^[#\-*]+\s*", "", base)
    # 去 create_ 前缀
    base = re.sub(r"^create_", "", base)
    # 去 concepts_ 前缀（LLM 有时把目录名拼进文件名）
    base = re.sub(r"^concepts_", "", base)
    # 去双重扩展名 (.md.md → .md)
    while base.endswith(".md.md"):
        base = base[:-3]
    # 去非法字符
    base = re.sub(r'[<>:"|?*]', "", base)
    # 去首尾空格和点
    base = base.strip(" .")

    result = dir_part + base if base else file_name

    # 确保概念文件在 concepts/ 下（除非是 index.md）
    if base and base.lower() != "index.md" and not result.startswith("concepts/"):
        result = "concepts/" + result

    return result


def _clean_tags(tags) -> list[str]:
    """清洗标签脏数据，返回干净的标签列表"""
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
    return clean_tags


def _build_body(title: str, tags: list[str], abstract: str, content: str = "") -> str:
    """生成标准页面模板（统一 MinIO/Local 两种模式的输出格式）"""
    import datetime
    tag_str = " ".join(_clean_tags(tags))
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    abs_text = abstract.replace("\\n", "\n")
    details = (content or "（等待后续扩展）").replace("\\n", "\n")
    return f"""# {title}

> **Tags:** {tag_str}
> **Created:** {date_str}

## Abstract
{abs_text}

## Details
{details}

## Related
- 

## References
- 
"""


# 💡 注意参数里多了 content
def create_page(file_name: str, title: str, tags: list[str], abstract: str, content: str = "") -> str:
    """严格按照 schema 模板创建新页面，包含模糊去重机制"""
    from pathlib import PurePosixPath

    file_name = _sanitize_filename(file_name)
    s = get_storage()
    key = _resolve_key(file_name)

    # 本地模式下确保目录存在
    path = _resolve(file_name)

    # ── 统一查重：模糊名称匹配（去 -/_/空格/.md 后比较） ──
    parent_prefix = str(PurePosixPath(key).parent) + "/"
    sibling_keys = s.list_keys(parent_prefix)
    clean_new = PurePosixPath(key).stem.lower().replace("-", "").replace("_", "").replace(" ", "")
    for k in sibling_keys:
        if k.endswith(".md"):
            clean_exist = PurePosixPath(k).stem.lower().replace("-", "").replace("_", "").replace(" ", "")
            if clean_new == clean_exist:
                return f"⚠️ 拦截重复：{k} 已存在，规避新建：{file_name}"

    # 生成标准页面内容（统一模板，消除两个分支的重复代码）
    body = _build_body(title, tags, abstract, content)
    s.write_text(key, body)
    return f"✅ 成功创建页面：{file_name}"


def str_replace(file_name: str, old_str: str, new_str: str) -> str:
    """极其精密的局部替换工具 (带空格宽容 + 活路径路由)"""
    s = get_storage()
    key = _resolve_key(file_name)

    if not s.exists(key):
        return f"❌ 错误：底层工具找不到文件 ({key})"

    content = s.read_text(key)

    # 1. 尝试绝对精确匹配
    if old_str in content:
        s.write_text(key, content.replace(old_str, new_str, 1))
        return f"✅ 成功修改文件：{file_name}"

    # 2. 尝试宽容匹配 (去掉大模型首尾乱加的换行和空格)
    old_str_clean = old_str.strip()
    if old_str_clean and old_str_clean in content:
        s.write_text(key, content.replace(old_str_clean, new_str, 1))
        return f"✅ 成功修改文件(启用宽容匹配)：{file_name}"

    return f"❌ 找不到旧文本，大模型可能产生了格式幻觉！\n寻找的: {repr(old_str)}"