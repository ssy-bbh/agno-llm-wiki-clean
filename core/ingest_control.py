"""
core/ingest_control.py — 摄入流水线控制（终止 / 继续）

基于文件系统实现跨 worker 控制，支持多进程 uvicorn 部署。
每个 user+workspace 独立管理终止标记和已处理概念检查点。
"""
import json
import time
from pathlib import Path

CONTROL_DIR = Path(__file__).resolve().parent.parent / "data" / ".ingest_control"


def _flag_path(user_id: str, workspace: str) -> Path:
    return CONTROL_DIR / f"{user_id}__{workspace}.flag"


def _checkpoint_path(user_id: str, workspace: str) -> Path:
    return CONTROL_DIR / f"{user_id}__{workspace}.checkpoint.json"


# ── 终止控制 ──

def request_terminate(user_id: str, workspace: str):
    """标记：请求终止当前摄入"""
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    _flag_path(user_id, workspace).write_text(
        json.dumps({"action": "terminate", "time": time.time()})
    )


def is_terminate_requested(user_id: str, workspace: str) -> bool:
    """检查是否收到终止请求"""
    return _flag_path(user_id, workspace).exists()


def clear_terminate(user_id: str, workspace: str):
    """清除终止标记"""
    fp = _flag_path(user_id, workspace)
    if fp.exists():
        fp.unlink()


# ── 概念检查点（用于 Resume 跳过已处理概念） ──

def _read_checkpoint(user_id: str, workspace: str) -> dict:
    cp = _checkpoint_path(user_id, workspace)
    if cp.exists():
        try:
            return json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"concepts": [], "files_done": [], "terminated_at": None}


def save_concept_checkpoint(user_id: str, workspace: str, concept_key: str):
    """记录一个已完成融合的概念"""
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    cp = _read_checkpoint(user_id, workspace)
    if concept_key not in cp["concepts"]:
        cp["concepts"].append(concept_key)
    _checkpoint_path(user_id, workspace).write_text(
        json.dumps(cp, ensure_ascii=False), encoding="utf-8"
    )


def save_file_checkpoint(user_id: str, workspace: str, filename: str):
    """记录一个已完整处理的文件"""
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    cp = _read_checkpoint(user_id, workspace)
    if filename not in cp["files_done"]:
        cp["files_done"].append(filename)
    _checkpoint_path(user_id, workspace).write_text(
        json.dumps(cp, ensure_ascii=False), encoding="utf-8"
    )


def is_concept_done(user_id: str, workspace: str, concept_key: str) -> bool:
    """检查某概念是否已在检查点中"""
    cp = _read_checkpoint(user_id, workspace)
    return concept_key in cp["concepts"]


def get_checkpoint(user_id: str, workspace: str) -> dict:
    """获取完整检查点信息"""
    return _read_checkpoint(user_id, workspace)


def clear_checkpoint(user_id: str, workspace: str):
    """清除检查点（全新开始）"""
    cp = _checkpoint_path(user_id, workspace)
    if cp.exists():
        cp.unlink()


def mark_terminated(user_id: str, workspace: str):
    """在检查点中标记终止时间"""
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    cp = _read_checkpoint(user_id, workspace)
    cp["terminated_at"] = time.time()
    _checkpoint_path(user_id, workspace).write_text(
        json.dumps(cp, ensure_ascii=False), encoding="utf-8"
    )
