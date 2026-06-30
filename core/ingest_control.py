"""
core/ingest_control.py — 摄入流水线控制（终止 / 继续 / SHUFFLE 缓存）

基于文件系统实现跨 worker 控制，支持多进程 uvicorn 部署。
每个 user+workspace 独立管理终止标记和检查点。

检查点设计（v2）：
- 保存 SHUFFLE 产出的完整 concept_payloads（待处理列表）
- 已融合概念从 pending 中移除
- resume 时直接从 pending 继续，不需要重跑 MAP+SHUFFLE
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


# ── 检查点 v2（待处理列表模式） ──

def _read_checkpoint(user_id: str, workspace: str) -> dict:
    cp = _checkpoint_path(user_id, workspace)
    if cp.exists():
        try:
            return json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "concept_payloads": {},  # {filename: {norm_key: payload_dict}}
        "files_done": [],        # 已完整处理（所有概念融合完毕）的文件
        "done_concepts": [],     # 已融合的概念 key 列表（用于兼容和统计）
        "terminated_at": None,
    }


def save_shuffle_result(user_id: str, workspace: str, filename: str,
                        payloads: dict):
    """
    保存某文件 SHUFFLE 产出的 concept_payloads（待处理列表）。
    payloads: {norm_key: {"primary_key", "display_name", "aliases", "texts", "summaries"}}
    注意：aliases 是 set，需要转 list 以 JSON 序列化。
    """
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    cp = _read_checkpoint(user_id, workspace)

    # 序列化 payloads（set → list）
    serialized = {}
    for k, v in payloads.items():
        serialized[k] = {
            "primary_key": v.get("primary_key", k),
            "display_name": v.get("display_name", k),
            "aliases": list(v.get("aliases", set())),
            "texts": v.get("texts", []),
            "summaries": v.get("summaries", []),
        }

    cp["concept_payloads"][filename] = serialized
    _checkpoint_path(user_id, workspace).write_text(
        json.dumps(cp, ensure_ascii=False), encoding="utf-8"
    )


def load_shuffle_cache(user_id: str, workspace: str) -> dict | None:
    """
    加载 SHUFFLE 缓存（concept_payloads）。
    返回: {filename: {norm_key: payload_dict}} 或 None（无缓存）。
    加载时将 list 转回 set（还原 aliases）。
    """
    cp = _read_checkpoint(user_id, workspace)
    raw = cp.get("concept_payloads", {})
    if not raw:
        return None

    # 反序列化（list → set）
    result = {}
    for filename, payloads in raw.items():
        file_payloads = {}
        for k, v in payloads.items():
            file_payloads[k] = {
                "primary_key": v.get("primary_key", k),
                "display_name": v.get("display_name", k),
                "aliases": set(v.get("aliases", [])),
                "texts": v.get("texts", []),
                "summaries": v.get("summaries", []),
            }
        result[filename] = file_payloads
    return result


def mark_concept_done(user_id: str, workspace: str, concept_key: str):
    """记录一个已完成融合的概念（保留在 payloads 中，供 resume 加载）"""
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    cp = _read_checkpoint(user_id, workspace)
    if concept_key not in cp["done_concepts"]:
        cp["done_concepts"].append(concept_key)
    # 不再从 payloads 中移除（resume 需要完整 payloads 才能跳过 MAP+SHUFFLE）
    # resume 时会检查 done_concepts 列表来跳过已完成的概念
    _checkpoint_path(user_id, workspace).write_text(
        json.dumps(cp, ensure_ascii=False), encoding="utf-8"
    )


def save_file_checkpoint(user_id: str, workspace: str, filename: str):
    """记录一个已完整处理的文件（所有概念已融合）"""
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    cp = _read_checkpoint(user_id, workspace)
    if filename not in cp["files_done"]:
        cp["files_done"].append(filename)
    # 文件完成 → 清除其 payloads（不再需要）
    cp.get("concept_payloads", {}).pop(filename, None)
    _checkpoint_path(user_id, workspace).write_text(
        json.dumps(cp, ensure_ascii=False), encoding="utf-8"
    )


def is_concept_done(user_id: str, workspace: str, concept_key: str) -> bool:
    """检查某概念是否已融合"""
    cp = _read_checkpoint(user_id, workspace)
    return concept_key in cp.get("done_concepts", [])


def get_pending_concepts(user_id: str, workspace: str) -> int:
    """统计所有文件中待处理的概念总数"""
    cache = load_shuffle_cache(user_id, workspace)
    if not cache:
        return 0
    done = set(_read_checkpoint(user_id, workspace).get("done_concepts", []))
    total = 0
    for payloads in cache.values():
        for k in payloads:
            if k not in done:
                total += 1
    return total


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
