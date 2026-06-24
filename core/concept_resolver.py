"""
concept_resolver.py — 公共概念别名匹配工具
将 autofill_flow.py 的 _get_aliases 算法抽出为共享函数，
供 graph API、lint_flow、autofill_flow 统一调用。
"""
import re
from pathlib import Path


def get_aliases(text: str) -> set:
    """
    从概念名中提取所有可能的别名（英文部分、中文部分、去符号全称）。
    例：
      "YOLOv8 (YOLOv8模型)" → {"yolov8", "yolov8模型", "yolov8(yolov8模型)"}
      "Fast R-CNN (快速区域卷积神经网络)" → {"fastrcnn", "快速区域卷积神经网络", "fastrcnn(快速区域卷积神经网络)"}
    """
    aliases = set()
    clean = text.lower().replace("-", "").replace("_", "").replace(" ", "")
    if clean:
        aliases.add(clean)

    match = re.match(r'^(.*?)\s*[\(（](.*?)[\)）]', text)
    if match:
        part1 = match.group(1).lower().replace("-", "").replace("_", "").replace(" ", "")
        part2 = match.group(2).lower().replace("-", "").replace("_", "").replace(" ", "")
        if part1:
            aliases.add(part1)
        if part2:
            aliases.add(part2)

    return aliases


def build_alias_index(files: list[Path]) -> dict:
    """
    从 .md 文件列表构建别名索引。
    返回: {alias_string → filename_stem} （多对一，后来者优先）
    """
    index = {}
    for f in files:
        if f.stem.lower() == "index":
            continue
        for alias in get_aliases(f.stem):
            index[alias] = f.stem
    return index


def resolve_link(link_text: str, alias_index: dict) -> str:
    """
    将 [[link_text]] 解析为真实的文件名 stem。
    返回匹配的 stem，找不到返回空字符串。
    """
    for alias in get_aliases(link_text):
        if alias in alias_index:
            return alias_index[alias]
    return ""
