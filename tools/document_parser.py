"""
document_parser.py — 文档解析与智能切片工具
"""
import os
from pathlib import Path

# 确保安装了依赖：pip install pdfplumber python-docx
try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import docx
except ImportError:
    docx = None


def extract_text(file_path: str) -> str:
    """自动识别后缀，提取纯文本"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"❌ 找不到文件：{file_path}")

    ext = path.suffix.lower()
    text = ""

    if ext == ".pdf":
        if not pdfplumber:
            raise ImportError("请先安装 pdfplumber: pip install pdfplumber")
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n\n"

    elif ext == ".docx":
        if not docx:
            raise ImportError("请先安装 python-docx: pip install python-docx")
        doc = docx.Document(path)
        text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

    elif ext in [".md", ".txt"]:
        text = path.read_text(encoding="utf-8")

    else:
        raise ValueError(f"⚠️ 暂不支持该文件格式解析：{ext}")

    return text


def chunk_text(text: str, chunk_size: int = 4000, overlap: int = 300) -> list[str]:
    """
    智能切片：带重叠的滑动窗口算法
    chunk_size: 每个切片的最大字符数
    overlap: 切片之间的重叠字符数，防止概念被生硬切断
    """
    if not text:
        return []

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size

        # 如果不是最后一块，尽量在换行符处切断，保持段落完整性
        if end < text_length:
            # 往回找最近的换行符
            last_newline = text.rfind('\n', start, end)
            if last_newline != -1 and last_newline > start + (chunk_size // 2):
                end = last_newline + 1  # 切在换行符之后

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # 下一个 chunk 的起点回退 overlap 的长度
        start = end - overlap

    return chunks