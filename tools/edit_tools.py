"""
edit_tools.py — 局部精准编辑工具 (纯手写安全版)
"""
import os
from pathlib import Path
# 锁定操作根目录，绝对不准越界
WIKI_ROOT = Path(__file__).parent.parent / "data" / "wiki"


def _resolve(file_name: str) -> Path:
    """将物理路径严格路由到对应的镜像目录，并剥夺大模型的路径控制权"""
    # 1. 从环境变量获取当前激活的资料库和子目录
    kb_name = os.environ.get("ACTIVE_KB", "default")
    sub_dir = os.environ.get("ACTIVE_SUBDIR", "")

    # 2. 拼装出完美的镜像物理路径：data/wiki/资料库名/子目录结构/
    base_dir = Path("data/wiki") / kb_name / sub_dir
    base_dir.mkdir(parents=True, exist_ok=True)

    # 3. 终极夺权：不管大模型在 JSON 里写的是 file: "concepts/YOLO.md" 还是 "核心算法/YOLO.md"
    # 我们只用 pure_name 提取纯文件名 "YOLO.md"，强行写入我们算好的镜像目录里！
    pure_name = Path(file_name).name

    return base_dir / pure_name


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
    body = f"""# {title}          和

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
    """极其精密的局部替换工具"""
    path = _resolve(file_name)

    if not path.exists():
        return f"❌ 错误：想要编辑的文件不存在 ({file_name})"

    content = path.read_text(encoding="utf-8")

    # 防弹锁：必须精确匹配到 old_str 才能替换
    if old_str not in content:
        return f"❌ 错误：在 {file_name} 中找不到指定的旧文本，拒绝修改！\n寻找的文本: {repr(old_str)}"

    # 只替换第一次出现的匹配项，防止误伤
    new_content = content.replace(old_str, new_str, 1)
    path.write_text(new_content, encoding="utf-8")

    return f"✅ 成功修改文件：{file_name}"