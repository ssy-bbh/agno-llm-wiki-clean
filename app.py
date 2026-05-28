"""
app.py — LLM-Wiki OS 后端中枢 (v0.2.0)
JWT 用户隔离 + 多轮会话记忆 + API Key 管理 + 报告合成
"""
import os
import sys
import re
import json
import uuid
import time
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

# 确保能正常加载同级及子目录模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ── 内部模块 ──
from core.path_resolver import (
    get_wiki_root, get_raw_root, get_concepts_dir, get_index_path,
    get_memory_db_path, ensure_user_dirs, list_workspaces, get_default_workspace,
    PROJECT_ROOT,
)
from core.auth import (
    AuthRequest, AuthResponse,
    register_user, login_user,
    get_current_user, get_optional_user, get_admin_user,
    save_user_api_key, get_user_api_keys,
)
from core.model_router import get_model_for_user, get_default_model, list_providers

from workflows.query_flow import QueryFlow
from workflows.lint_flow import LintFlow
from workflows.autofill_flow import AutoFillFlow
from workflows.ingest_flow import IngestFlow
from core.task_log import task_log, TaskOutputCapture


# ==========================================
# 🚀 应用生命周期
# ==========================================
@asynccontextmanager
async def lifespan(application: FastAPI):
    """启动 / 关闭钩子"""
    # 启动时初始化
    _init_memory_db()
    print("🧠 LLM-Wiki OS v0.2.0 已启动")
    yield
    print("👋 LLM-Wiki OS 正在关闭...")


app = FastAPI(title="LLM-Wiki OS Backend", version="0.2.0", lifespan=lifespan)

# CORS（生产环境应改为白名单）
_cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# 🧠 Agno 记忆数据库（单例）
# ==========================================
_memory_db = None


def _init_memory_db():
    global _memory_db
    from agno.db.sqlite import SqliteDb
    db_path = get_memory_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _memory_db = SqliteDb(db_file=str(db_path))
    # 启用 WAL 模式以支持并发读写
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.close()
    print(f"📦 Memory DB: {db_path}")


def get_memory_db():
    """获取全局 Agno SqliteDb 实例"""
    if _memory_db is None:
        _init_memory_db()
    return _memory_db


# ==========================================
# 🏭 工作流工厂（按 user_id 动态创建）
# ==========================================
_query_flow_cache: Dict[str, QueryFlow] = {}


def get_query_flow(user_id: str = "") -> QueryFlow:
    """获取用户专属 QueryFlow 实例"""
    if user_id not in _query_flow_cache:
        _query_flow_cache[user_id] = QueryFlow(user_id=user_id)
    return _query_flow_cache[user_id]


# LintFlow / AutoFillFlow 保持全局，但传入 user_id
lint_flow = LintFlow()
autofill_flow = AutoFillFlow(threshold=5)


# ==========================================
# 📋 Pydantic 数据模型
# ==========================================
class ChatRequest(BaseModel):
    query: str
    workspace: Optional[str] = ""
    history: List[Dict[str, Any]] = []
    intent_override: Optional[str] = None
    session_id: Optional[str] = ""


class ForgeRequest(BaseModel):
    action: str
    workspace: str


class SandboxCreate(BaseModel):
    name: str


class FileEditRequest(BaseModel):
    workspace: str
    file_id: str
    content: str


class ApiKeySaveRequest(BaseModel):
    provider: str
    api_key: str
    base_url: str = ""
    model_id: str = ""


class ReportRequest(BaseModel):
    topic: str
    workspace: str
    outline: Optional[str] = ""
    session_id: Optional[str] = ""


# ==========================================
# 🧠 意图路由器 (LLM Agent)
# ==========================================
class Intent:
    CHAT = "chat"
    SCAN = "scan"
    SUMMARY = "summary"
    QUERY = "query"
    ERROR = "error"


from pydantic import BaseModel as _PB, Field as _F
from typing import Literal as _L


class _IntentDecision(_PB):
    intent: _L["chat", "scan", "summary", "query"] = _F(
        description="chat(闲聊)/scan(扫描)/summary(概览)/query(知识查询)"
    )


class IntentRouter:
    def __init__(self):
        from agno.agent import Agent
        self.agent = Agent(
            model=get_default_model(),
            instructions=[
                "你是一个意图分类器。根据用户输入判断意图。",
                "- chat：打招呼、闲聊、夸赞、问AI身份",
                "- scan：询问知识库有什么概念/节点",
                "- summary：总结/概览知识库",
                "- query：具体知识问题，需检索资料",
                "不确定时优先 query。"
            ],
            output_schema=_IntentDecision,
            stream=False,
        )

    def classify(self, query: str) -> str:
        if not query or not query.strip():
            return Intent.ERROR
        q = query.strip()
        if len(q) <= 3 and re.match(r'^[\s\u4e00-\u9fa5a-zA-Z]{1,3}$', q):
            return Intent.CHAT
        try:
            result = self.agent.run(q)
            if hasattr(result.content, 'model_dump'):
                return result.content.model_dump()['intent']
            if hasattr(result.content, 'intent'):
                return result.content.intent
            text = str(result.content).lower()
            for tag in ['chat', 'scan', 'summary', 'query']:
                if tag in text:
                    return tag
        except Exception:
            pass
        return Intent.QUERY


_intent_router = None


def classify_intent(query: str) -> str:
    global _intent_router
    if _intent_router is None:
        _intent_router = IntentRouter()
    return _intent_router.classify(query)


# ==========================================
# 🏥 健康检查
# ==========================================
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "version": "0.2.0",
        "timestamp": time.time(),
        "memory_db": str(get_memory_db_path()),
    }


# ==========================================
# 🔐 认证端点
# ==========================================
@app.post("/api/auth/register", response_model=AuthResponse)
async def api_register(req: AuthRequest):
    try:
        return register_user(req.username, req.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/auth/login", response_model=AuthResponse)
async def api_login(req: AuthRequest):
    try:
        return login_user(req.username, req.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.get("/api/auth/me")
async def api_me(user=Depends(get_current_user)):
    return {"user_id": user["user_id"], "username": user["username"]}


# ==========================================
# 🔑 API Key 管理
# ==========================================
@app.get("/api/settings/providers")
async def api_list_providers(user=Depends(get_current_user)):
    """列出所有模型提供商 + 用户已配置的"""
    providers = list_providers()
    user_keys = get_user_api_keys(user["user_id"])
    for p in providers:
        p["configured"] = p["id"] in user_keys
        if p["id"] in user_keys:
            p["user_config"] = user_keys[p["id"]]
    return providers


@app.post("/api/settings/api-key")
async def api_save_key(req: ApiKeySaveRequest, user=Depends(get_current_user)):
    """保存用户 API Key"""
    if not req.api_key or len(req.api_key) < 8:
        raise HTTPException(status_code=400, detail="API Key 太短")
    ok = save_user_api_key(user["user_id"], req.provider, req.api_key, req.base_url, req.model_id)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"status": "success", "provider": req.provider}


# ==========================================
# 📝 会话历史管理
# ==========================================
@app.get("/api/sessions")
async def api_list_sessions(
    workspace: str = Query(default=""),
    user=Depends(get_current_user),
):
    """列出用户在指定工作区的历史会话"""
    db = get_memory_db()
    user_id = user["user_id"]
    from agno.db.base import SessionType
    all_sessions = db.get_sessions(user_id=user_id, session_type=SessionType.AGENT)

    # 按工作区前缀过滤
    prefix = f"{user_id}:{workspace}:" if workspace else f"{user_id}:"
    filtered = []
    for s in all_sessions:
        sid = s.session_id if hasattr(s, 'session_id') else (s.get('session_id', '') if isinstance(s, dict) else '')
        if sid.startswith(prefix):
            entry = {
                "session_id": sid,
                "created_at": getattr(s, 'created_at', None) or (s.get('created_at') if isinstance(s, dict) else None),
                "updated_at": getattr(s, 'updated_at', None) or (s.get('updated_at') if isinstance(s, dict) else None),
            }
            # 尝试提取 session name
            session_data = getattr(s, 'session_data', None) or (s.get('session_data') if isinstance(s, dict) else None)
            if session_data and isinstance(session_data, dict):
                entry["name"] = session_data.get("session_name", "")
            else:
                entry["name"] = ""
            filtered.append(entry)

    # 按 updated_at 倒序
    filtered.sort(key=lambda x: x.get("updated_at") or 0, reverse=True)
    return filtered


@app.post("/api/sessions/create")
async def api_create_session(
    workspace: str = Query(default=""),
    user=Depends(get_current_user),
):
    """创建新会话，返回 session_id"""
    uid = user["user_id"]
    ws = workspace or "global"
    session_id = f"{uid}:{ws}:{uuid.uuid4().hex[:12]}"
    return {"session_id": session_id, "workspace": ws}


@app.delete("/api/sessions/{session_id}")
async def api_delete_session(session_id: str, user=Depends(get_current_user)):
    """删除指定会话"""
    uid = user["user_id"]
    if not session_id.startswith(f"{uid}:"):
        raise HTTPException(status_code=403, detail="无权删除此会话")

    db = get_memory_db()
    try:
        db.delete_session(session_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}/messages")
async def api_get_session_messages(session_id: str, user=Depends(get_current_user)):
    """获取指定会话的历史消息"""
    uid = user["user_id"]
    if not session_id.startswith(f"{uid}:"):
        raise HTTPException(status_code=403, detail="无权查看此会话")

    try:
        import sqlite3 as _sqlite
        db_path = str(get_memory_db_path())
        conn = _sqlite.connect(db_path)
        try:
            row = conn.execute(
                "SELECT runs FROM agno_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if not row:
                return {"session_id": session_id, "messages": []}

            messages = []
            runs_raw = row[0]
            if runs_raw:
                runs = json.loads(runs_raw) if isinstance(runs_raw, str) else runs_raw
                if isinstance(runs, str):
                    runs = json.loads(runs)
                for run in runs:
                    if isinstance(run, str):
                        run = json.loads(run)
                    run_msgs = run.get('messages', [])
                    if isinstance(run_msgs, str):
                        run_msgs = json.loads(run_msgs)
                    for m in run_msgs:
                        if isinstance(m, str):
                            m = json.loads(m)
                        role = m.get('role', '')
                        content = m.get('content', '')
                        if role in ('user', 'assistant') and content:
                            messages.append({"role": role, "content": str(content)[:5000]})

            return {"session_id": session_id, "messages": messages}
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 🔍 管理员监控 API
# ==========================================
@app.get("/api/admin/users")
async def admin_list_users(admin=Depends(get_admin_user)):
    """列出所有用户及其统计信息"""
    import sqlite3 as _sqlite
    conn = _sqlite.connect(str(get_memory_db_path()))
    try:
        # 从 users.db 获取用户列表
        uconn = _sqlite.connect(str(PROJECT_ROOT / "data" / "users.db"))
        uconn.row_factory = _sqlite.Row
        try:
            users = uconn.execute(
                "SELECT user_id, username, role, created_at FROM users ORDER BY created_at DESC"
            ).fetchall()
            result = []
            for u in users:
                # 统计该用户的会话数
                session_count = conn.execute(
                    "SELECT COUNT(*) FROM agno_sessions WHERE user_id = ?", (u["user_id"],)
                ).fetchone()[0]
                # 最新消息时间
                last_row = conn.execute(
                    "SELECT MAX(updated_at) FROM agno_sessions WHERE user_id = ?", (u["user_id"],)
                ).fetchone()
                last_active = last_row[0] if last_row and last_row[0] else None
                result.append({
                    "user_id": u["user_id"],
                    "username": u["username"],
                    "role": u["role"] if "role" in u.keys() else "user",
                    "created_at": u["created_at"],
                    "session_count": session_count,
                    "last_active": last_active,
                })
            return result
        finally:
            uconn.close()
    finally:
        conn.close()


@app.get("/api/admin/sessions")
async def admin_list_all_sessions(
    user_id: str = Query(default=""),
    admin=Depends(get_admin_user),
):
    """列出所有用户的会话（管理员视角）"""
    import sqlite3 as _sqlite
    db_path = str(get_memory_db_path())
    conn = _sqlite.connect(db_path)
    conn.row_factory = _sqlite.Row
    try:
        if user_id:
            rows = conn.execute(
                "SELECT session_id, user_id, session_data, created_at, updated_at FROM agno_sessions WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT session_id, user_id, session_data, created_at, updated_at FROM agno_sessions ORDER BY updated_at DESC LIMIT 200"
            ).fetchall()

        sessions = []
        for r in rows:
            entry = {
                "session_id": r["session_id"],
                "user_id": r["user_id"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "name": "",
            }
            sd = json.loads(r["session_data"]) if r["session_data"] else {}
            if isinstance(sd, dict):
                entry["name"] = sd.get("session_name", "")
            sessions.append(entry)
        return sessions
    finally:
        conn.close()


@app.get("/api/admin/logs")
async def admin_stream_logs(request: Request, admin=Depends(get_admin_user)):
    """管理员实时日志流 (SSE) — 推送 systemd journal"""
    import subprocess

    async def log_stream():
        # 先发送最近 200 行历史日志
        try:
            result = subprocess.run(
                ["journalctl", "-u", "llm-wiki", "-n", "200", "--no-pager", "-o", "short-iso"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines():
                yield f"data: {json.dumps({'type': 'log', 'content': line})}\n\n"
        except Exception as e:
            # 非 systemd 环境（本地开发），读取 uvicorn 日志文件或提示
            yield f"data: {json.dumps({'type': 'log', 'content': f'⚠️ 无法读取 journalctl: {e}'})}\n\n"
            yield f"data: {json.dumps({'type': 'log', 'content': '提示: journalctl 仅在 systemd 管理的服务器上可用'})}\n\n"

        yield f"data: {json.dumps({'type': 'log', 'content': '── 历史日志结束，以下为实时推送 ──'})}\n\n"

        # 实时跟踪新日志
        try:
            proc = subprocess.Popen(
                ["journalctl", "-u", "llm-wiki", "-f", "--no-pager", "-o", "short-iso"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            import asyncio
            while True:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, proc.stdout.readline
                )
                if not line:
                    break
                line = line.rstrip('\n')
                if line:
                    yield f"data: {json.dumps({'type': 'log', 'content': line})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'log', 'content': f'⚠️ 日志流断开: {e}'})}\n\n"

    return StreamingResponse(log_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/admin/server-status")
async def admin_server_status(admin=Depends(get_admin_user)):
    """服务器运行状态概览"""
    import subprocess
    info = {}
    try:
        r = subprocess.run(["systemctl", "is-active", "llm-wiki"], capture_output=True, text=True, timeout=5)
        info["service"] = r.stdout.strip()
    except Exception:
        info["service"] = "unknown"
    try:
        r = subprocess.run(["uptime"], capture_output=True, text=True, timeout=5)
        info["uptime"] = r.stdout.strip()
    except Exception:
        info["uptime"] = "unknown"
    try:
        r = subprocess.run(["df", "-h", "/mnt/vdb"], capture_output=True, text=True, timeout=5)
        lines = r.stdout.strip().splitlines()
        info["disk"] = lines[-1] if len(lines) > 1 else "unknown"
    except Exception:
        info["disk"] = "unknown"
    try:
        r = subprocess.run(["free", "-h"], capture_output=True, text=True, timeout=5)
        lines = r.stdout.strip().splitlines()
        info["memory"] = lines[1] if len(lines) > 1 else "unknown"
    except Exception:
        info["memory"] = "unknown"
    return info


# ==========================================
# 📋 任务日志 (Task Logs)
# ==========================================
@app.get("/api/admin/task-logs")
async def admin_list_task_logs(admin=Depends(get_admin_user)):
    """列出所有有任务日志的 user:workspace 组合"""
    return task_log.list_keys()


@app.get("/api/admin/task-logs/{user_id}/{workspace}")
async def admin_get_task_logs(user_id: str, workspace: str, limit: int = 500, since: float = 0, admin=Depends(get_admin_user)):
    """获取指定 user:workspace 的任务日志"""
    logs = task_log.get_logs(user_id=user_id, workspace=workspace, limit=limit, since=since)
    return {"user_id": user_id, "workspace": workspace, "logs": logs, "total": len(logs)}


@app.get("/api/admin/task-logs/{user_id}/{workspace}/stream")
async def admin_stream_task_logs(user_id: str, workspace: str, request: Request, admin=Depends(get_admin_user)):
    """SSE 实时推送任务日志"""
    import asyncio

    async def stream():
        last_ts = 0
        # 先发送历史日志
        history = task_log.get_logs(user_id=user_id, workspace=workspace, limit=200)
        for entry in history:
            yield f"data: {json.dumps(entry)}\n\n"
            last_ts = max(last_ts, entry.get("timestamp", 0))
        yield f"data: {json.dumps({'time': '', 'message': '── 历史日志结束，以下为实时推送 ──', 'level': 'info'})}\n\n"

        # 实时轮询新日志
        while True:
            if await request.is_disconnected():
                break
            new_logs = task_log.get_logs(user_id=user_id, workspace=workspace, limit=50, since=last_ts)
            for entry in new_logs:
                ts = entry.get("timestamp", 0)
                if ts > last_ts:
                    yield f"data: {json.dumps(entry)}\n\n"
                    last_ts = ts
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.delete("/api/admin/task-logs/{user_id}/{workspace}")
async def admin_clear_task_logs(user_id: str, workspace: str, admin=Depends(get_admin_user)):
    """清除指定 user:workspace 的任务日志"""
    task_log.clear(user_id=user_id, workspace=workspace)
    return {"status": "cleared"}


@app.get("/api/admin/sessions/{session_id}/messages")
async def admin_get_session_messages(session_id: str, admin=Depends(get_admin_user)):
    """管理员查看任意用户的会话消息"""
    import sqlite3 as _sqlite
    db_path = str(get_memory_db_path())
    conn = _sqlite.connect(db_path)
    try:
        row = conn.execute(
            "SELECT runs, user_id FROM agno_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if not row:
            return {"session_id": session_id, "messages": []}

        messages = []
        runs_raw = row[0]
        if runs_raw:
            runs = json.loads(runs_raw) if isinstance(runs_raw, str) else runs_raw
            if isinstance(runs, str):
                runs = json.loads(runs)
            for run in runs:
                if isinstance(run, str):
                    run = json.loads(run)
                run_msgs = run.get('messages', [])
                if isinstance(run_msgs, str):
                    run_msgs = json.loads(run_msgs)
                for m in run_msgs:
                    if isinstance(m, str):
                        m = json.loads(m)
                    role = m.get('role', '')
                    content = m.get('content', '')
                    if role in ('user', 'assistant') and content:
                        messages.append({"role": role, "content": str(content)[:5000]})

        return {"session_id": session_id, "user_id": row[1], "messages": messages}
    finally:
        conn.close()


# ==========================================
# 🗣️ 1. 探求模式接口 (Query Mode)
# ==========================================
@app.get("/api/intent/debug")
async def debug_intent(query: str, user=Depends(get_current_user)):
    return {"intent": classify_intent(query), "query": query}


@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest, user=Depends(get_current_user)):
    """流式应答中枢 — 五向意图分发器"""
    try:
        query = request.query.strip()
        workspace = request.workspace
        user_id = user["user_id"]
        session_id = request.session_id or f"{user_id}:{workspace or 'global'}:{uuid.uuid4().hex[:12]}"

        if request.intent_override and request.intent_override in (
            Intent.CHAT, Intent.SCAN, Intent.SUMMARY, Intent.QUERY
        ):
            intent = request.intent_override
        else:
            intent = classify_intent(query)

        print(f"🧠 [{user_id}] '{query[:40]}' -> {intent}")

        if intent == Intent.ERROR:
            async def error_stream():
                yield f"data: {json.dumps({'type': 'text', 'content': '⚠️ 请输入你的问题或指令。'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return StreamingResponse(error_stream(), media_type="text/event-stream")

        if intent == Intent.CHAT:
            return StreamingResponse(
                _wrap_stream_with_save(
                    _stream_chat_reply(query, history=request.history, user_id=user_id, session_id=session_id),
                    user_id, session_id, query
                ),
                media_type="text/event-stream",
            )

        if intent == Intent.SCAN:
            return StreamingResponse(
                _wrap_stream_with_save(
                    _stream_scan_response(query, workspace, user_id),
                    user_id, session_id, query
                ),
                media_type="text/event-stream",
            )

        if intent == Intent.SUMMARY:
            return StreamingResponse(
                _wrap_stream_with_save(
                    _stream_summary_response(query, workspace, user_id, session_id),
                    user_id, session_id, query
                ),
                media_type="text/event-stream",
            )

        # QUERY 模式
        qf = get_query_flow(user_id)
        return StreamingResponse(
            _wrap_stream_with_save(
                qf.stream_execute(
                    user_question=query,
                    target_workspace=workspace,
                    history=request.history,
                    user_id=user_id,
                    session_id=session_id,
                ),
                user_id, session_id, query
            ),
            media_type="text/event-stream",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
#  📦 会话持久化（统一存储所有意图的对话）
# ==========================================
def _save_session_message(user_id: str, session_id: str, user_msg: str, assistant_msg: str):
    """将一轮对话追加到 agno_sessions 表"""
    import sqlite3 as _sqlite
    db_path = str(get_memory_db_path())
    conn = _sqlite.connect(db_path)
    try:
        # 确保表存在
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agno_sessions (
                session_id TEXT PRIMARY KEY,
                session_type TEXT DEFAULT 'agent',
                agent_id TEXT,
                team_id TEXT,
                workflow_id TEXT,
                user_id TEXT,
                session_data TEXT,
                agent_data TEXT,
                team_data TEXT,
                workflow_data TEXT,
                metadata TEXT,
                runs TEXT,
                summary TEXT,
                created_at REAL,
                updated_at REAL
            )
        """)

        now = time.time()
        new_run = {
            "run_id": uuid.uuid4().hex,
            "user_id": user_id,
            "session_id": session_id,
            "messages": [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": assistant_msg[:5000]},
            ],
            "created_at": now,
            "status": "completed",
        }

        row = conn.execute(
            "SELECT runs, session_data FROM agno_sessions WHERE session_id = ?",
            (session_id,)
        ).fetchone()

        if row:
            runs = json.loads(row[0]) if row[0] else []
            runs.append(new_run)
            conn.execute(
                "UPDATE agno_sessions SET runs = ?, updated_at = ? WHERE session_id = ?",
                (json.dumps(runs, ensure_ascii=False), now, session_id)
            )
        else:
            # 新会话：用第一条用户消息作为会话名
            session_name = user_msg[:30].strip()
            if len(user_msg) > 30:
                session_name += "..."
            session_data = json.dumps({"session_name": session_name}, ensure_ascii=False)
            conn.execute(
                "INSERT INTO agno_sessions (session_id, session_type, user_id, session_data, runs, created_at, updated_at) VALUES (?, 'agent', ?, ?, ?, ?, ?)",
                (session_id, user_id, session_data, json.dumps([new_run], ensure_ascii=False), now, now)
            )
        conn.commit()
    except Exception as e:
        print(f"  [WARN] save session error: {e}")
    finally:
        conn.close()


async def _wrap_stream_with_save(stream_gen, user_id, session_id, user_query):
    """包装 SSE 流，在流结束时自动保存对话到 DB"""
    assistant_text = ""
    try:
        async for chunk in stream_gen:
            # 从 SSE chunk 中提取 assistant 文本
            if chunk.startswith("data: "):
                try:
                    data = json.loads(chunk[6:].strip())
                    if data.get("type") == "text":
                        assistant_text += data.get("content", "")
                except:
                    pass
            yield chunk
    finally:
        if assistant_text:
            _save_session_message(user_id, session_id, user_query, assistant_text)


# ==========================================
#  意图分轨处理函数
# ==========================================
async def _stream_chat_reply(query: str, history: list = None, user_id: str = "", session_id: str = ""):
    """闲聊轨道：LLM 直接回复，挂载 db 实现多轮记忆"""
    from agno.agent import Agent

    model = get_model_for_user(user_id)
    agent = Agent(
        model=model,
        instructions=[
            "你是一个 AI 向导，回答简短、有趣、有个性。",
            "不要调用任何外部工具或知识库，直接基于你的常识回复。",
            "回复控制在 100 字以内。",
        ],
        stream=True,
    )

    system_prompt = f"用户说：{query}"
    if history:
        ctx = "【前情回顾】\n"
        for msg in history[-5:]:
            role = "用户" if msg.get('role') == 'user' else 'AI'
            ctx += f"{role}: {msg.get('content')}\n"
        system_prompt = f"{ctx}\n用户最新消息：{query}"

    try:
        response = agent.run(system_prompt)
        for chunk in response:
            text = chunk.content if hasattr(chunk, 'content') else str(chunk)
            if text and text != "None":
                yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'text', 'content': f'⚠️ 闲聊模块异常: {str(e)}'})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def _stream_scan_response(query: str, workspace: str, user_id: str = ""):
    """扫描轨道：全局 or 指定沙箱"""
    import asyncio

    wiki_base = get_wiki_root(user_id)

    if not workspace or not workspace.strip():
        all_ws = list_workspaces(user_id)
        if not all_ws:
            content = "🔭 系统中尚未创建任何知识沙箱。\n\n请先创建沙箱并摄入原始资料。"
            yield f"data: {json.dumps({'type': 'log', 'content': '📡 [全局扫描] 未找到任何沙箱'})}\n\n"
            for i in range(0, len(content), 15):
                yield f"data: {json.dumps({'type': 'text', 'content': content[i:i+15]})}\n\n"
                await asyncio.sleep(0.02)
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        yield f"data: {json.dumps({'type': 'log', 'content': f'📡 [全局扫描] 正在扫描 {len(all_ws)} 个沙箱 ...'})}\n\n"
        await asyncio.sleep(0.3)

        total_nodes = 0
        ws_stats = []
        for ws_name in all_ws:
            concepts_dir = get_concepts_dir(user_id, ws_name)
            count = 0
            if concepts_dir.exists():
                count = len([f for f in concepts_dir.glob("*.md") if f.stem.lower() != "index"])
            total_nodes += count
            ws_stats.append((ws_name, count))

        lines = [f"📡 全局扫描完毕，共检测到 **{len(all_ws)}** 个沙箱 / **{total_nodes}** 个知识节点：\n"]
        lines.append("| 沙箱 | 节点数 | 状态 |")
        lines.append("|------|--------|------|")
        for ws_name, count in ws_stats:
            status = "✅ 已激活" if count > 0 else "⭕ 虚空"
            lines.append(f"| {ws_name} | {count} | {status} |")
        lines.append("\n💡 在左侧切换沙箱隔离区可深入查看具体节点。")
        content = "\n".join(lines)
        for i in range(0, len(content), 15):
            yield f"data: {json.dumps({'type': 'text', 'content': content[i:i+15]})}\n\n"
            await asyncio.sleep(0.02)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    # 指定沙箱扫描
    concepts_dir = get_concepts_dir(user_id, workspace)
    available = []
    if concepts_dir.exists():
        available = sorted([f.stem for f in concepts_dir.glob("*.md") if f.stem.lower() != "index"])

    if available:
        group_size = 8
        groups = [available[i:i + group_size] for i in range(0, len(available), group_size)]
        display_lines = [f"📡 扫描完毕，在沙箱 **{workspace}** 中检测到 **{len(available)}** 个知识节点：\n"]
        for group in groups:
            display_lines.append(f"{' | '.join(f'`{c}`' for c in group)}")
        display_lines.append(f"\n💡 点击图谱节点或直接输入问题即可深入探索。")
        content = "\n".join(display_lines)
    else:
        content = (f"🔭 沙箱 **{workspace}** 中尚未生成任何知识节点。\n\n"
                   f"试着拖拽一些原始资料到赛博熔炉中进行首次摄入吧！")

    yield f"data: {json.dumps({'type': 'log', 'content': f'📡 [扫描] 正在读取沙箱 [{workspace}] ...'})}\n\n"
    await asyncio.sleep(0.3)
    for i in range(0, len(content), 15):
        yield f"data: {json.dumps({'type': 'text', 'content': content[i:i+15]})}\n\n"
        await asyncio.sleep(0.02)
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def _stream_summary_response(query: str, workspace: str, user_id: str = "", session_id: str = ""):
    """概览轨道：读取 index.md + LLM 总结，挂载 db"""
    import asyncio
    from agno.agent import Agent

    if not workspace or not workspace.strip():
        workspace = get_default_workspace(user_id)
        if not workspace:
            content = "📋 系统中尚未创建任何知识沙箱，无法生成概览。"
            for i in range(0, len(content), 15):
                yield f"data: {json.dumps({'type': 'text', 'content': content[i:i+15]})}\n\n"
                await asyncio.sleep(0.02)
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

    index_path = get_index_path(user_id, workspace)
    yield f"data: {json.dumps({'type': 'log', 'content': '📋 [概览] 正在读取导航地图 ...'})}\n\n"
    await asyncio.sleep(0.3)

    if index_path.exists():
        index_content = index_path.read_text(encoding="utf-8")
        if len(index_content.strip()) < 50:
            content = f"📋 沙箱 **{workspace}** 的导航地图几乎空白。\n\n建议先进行知识摄入。"
            for i in range(0, len(content), 15):
                yield f"data: {json.dumps({'type': 'text', 'content': content[i:i+15]})}\n\n"
                await asyncio.sleep(0.02)
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        model = get_model_for_user(user_id)
        agent = Agent(
            model=model,
            db=get_memory_db(),
            user_id=user_id,
            session_id=session_id,
            num_history_runs=5,
            instructions=[
                "你是一位知识库架构师。根据导航地图总结核心内容领域和知识结构。",
                "回答控制在 200 字以内，使用 Markdown 格式。",
            ],
            stream=True,
        )
        prompt = f"【用户问题】: {query}\n\n【导航地图】:\n{index_content[:4000]}"
        try:
            response = agent.run(prompt)
            for chunk in response:
                text = chunk.content if hasattr(chunk, 'content') else str(chunk)
                if text and text != "None":
                    yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'text', 'content': f'⚠️ 概览模块异常: {str(e)}'})}\n\n"
    else:
        content = f"📋 沙箱 **{workspace}** 中尚未建立导航地图。\n\n建议先摄入原始资料。"
        for i in range(0, len(content), 15):
            yield f"data: {json.dumps({'type': 'text', 'content': content[i:i+15]})}\n\n"
            await asyncio.sleep(0.02)
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ==========================================
# 🕸️ 2. 织网模式 (Forge Mode)
# ==========================================
@app.post("/api/forge")
async def forge_endpoint(request: ForgeRequest, user=Depends(get_current_user)):
    if not request.workspace:
        raise HTTPException(status_code=400, detail="必须指定隔离沙箱！")

    user_id = user["user_id"]

    async def run_forge_task():
        action_name = "织网" if request.action == "reweave" else "填补黑洞" if request.action == "fill_blackhole" else request.action
        task_log.append(user_id, request.workspace, f"🔥 [锻造炉] 启动: {action_name}", "info")
        try:
            if request.action == "reweave":
                async for log in lint_flow.stream_run(request.workspace, user_id=user_id):
                    # 同时写入任务日志
                    try:
                        data = json.loads(log.replace("data: ", "").strip())
                        if data.get("type") == "log":
                            task_log.append(user_id, request.workspace, data["content"])
                    except Exception:
                        pass
                    yield log
            elif request.action == "fill_blackhole":
                async for log in autofill_flow.stream_run(request.workspace, user_id=user_id):
                    try:
                        data = json.loads(log.replace("data: ", "").strip())
                        if data.get("type") == "log":
                            task_log.append(user_id, request.workspace, data["content"])
                    except Exception:
                        pass
                    yield log
            else:
                yield f"data: {json.dumps({'type': 'log', 'content': '❌ 未知的织网指令。'})}\n\n"
        except Exception as e:
            task_log.append(user_id, request.workspace, f"💥 熔炉崩溃: {str(e)}", "error")
            yield f"data: {json.dumps({'type': 'log', 'content': f'💥 熔炉崩溃: {str(e)}'})}\n\n"
        task_log.append(user_id, request.workspace, f"✅ [锻造炉] {action_name} 完成", "success")
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(run_forge_task(), media_type="text/event-stream")


# ==========================================
# 🗂️ 3. 沙箱管理
# ==========================================
@app.post("/api/workspaces/create")
async def create_workspace(req: SandboxCreate, user=Depends(get_current_user)):
    user_id = user["user_id"]
    safe_name = re.sub(r'[\\/*?:"<>|]', "", req.name).strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="非法的沙箱名称！")

    wiki_dir = get_wiki_root(user_id) / safe_name / "concepts"
    raw_dir = get_raw_root(user_id) / safe_name

    try:
        wiki_dir.mkdir(parents=True, exist_ok=True)
        raw_dir.mkdir(parents=True, exist_ok=True)
        return {"status": "success", "workspace": safe_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"开荒失败: {str(e)}")


# ==========================================
# 📥 4. 文件上传（含校验）
# ==========================================
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".pptx", ".ppt", ".xlsx", ".csv", ".html"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@app.post("/api/upload")
async def upload_batch_endpoint(
    workspace: str = Form(...),
    files: List[UploadFile] = File(...),
    user=Depends(get_current_user),
):
    user_id = user["user_id"]
    if not workspace:
        raise HTTPException(status_code=400, detail="必须指定目标沙箱！")
    if not files:
        raise HTTPException(status_code=400, detail="未检测到任何文件！")

    # 文件校验
    for f in files:
        ext = Path(f.filename).suffix.lower() if f.filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}")
        if f.size and f.size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"文件 {f.filename} 超过 50MB 限制")

    raw_dir = get_raw_root(user_id) / workspace
    raw_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    try:
        for f in files:
            file_path = raw_dir / f.filename
            contents = await f.read()
            file_path.write_bytes(contents)
            saved_paths.append(file_path)

        # 后台线程：用参数传递代替 os.environ 污染，输出捕获到任务日志
        def run_background_batch():
            with TaskOutputCapture(user_id=user_id, workspace=workspace):
                task_log.append(user_id, workspace, f"🚀 [批量摄入流] 启动，共 {len(saved_paths)} 个文件", "info")
                flow = IngestFlow()
                for fp in saved_paths:
                    print(f"\n🚀 [{user_id}] 提取: {fp.name} -> {workspace}")
                    try:
                        flow.run(str(fp), kb_name=workspace, user_id=user_id)
                    except Exception as e:
                        print(f"❌ 提取 {fp.name} 失败: {e}")
                task_log.append(user_id, workspace, f"✅ [{user_id}] 批量提炼完成！共处理 {len(saved_paths)} 个文件", "success")

        threading.Thread(target=run_background_batch, daemon=True).start()

        return {
            "status": "success",
            "message": f"成功落盘 {len(files)} 个文件",
            "files": [f.filename for f in files],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"落盘失败: {str(e)}")


# ==========================================
# 🔍 5. 基础接口 (Workspaces & Graph)
# ==========================================
@app.get("/api/workspaces")
async def get_workspaces(user=Depends(get_current_user)):
    user_id = user["user_id"]
    return list_workspaces(user_id)


@app.get("/api/graph")
async def get_graph(workspace: str, user=Depends(get_current_user)):
    user_id = user["user_id"]
    base_dir = get_wiki_root(user_id) / workspace
    concepts_dir = base_dir / "concepts"
    search_dir = concepts_dir if concepts_dir.exists() else base_dir

    if not base_dir.exists():
        return {"nodes": [], "links": []}

    nodes, links, node_set = [], [], set()
    try:
        for fp in search_dir.rglob("*.md"):
            name = fp.stem
            if name.lower() == "index":
                continue
            nodes.append({"id": name, "group": 1})
            node_set.add(name.lower())

        for fp in search_dir.rglob("*.md"):
            source = fp.stem
            if source.lower() == "index":
                continue
            content = fp.read_text(encoding="utf-8")
            for match in re.findall(r'\[\[(.*?)\]\]', content):
                target = match.split("|")[0].strip()
                if target.lower() == "index":
                    continue
                if target.lower() in node_set:
                    links.append({"source": source, "target": target})

        return {"nodes": nodes, "links": links}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 📥 6. 隔离审批区 (Inbox)
# ==========================================
DRAFT_TAG = "<" + "!-- AUTOFILL_DRAFT --" + ">"


@app.get("/api/inbox")
async def get_inbox(workspace: str, user=Depends(get_current_user)):
    if not workspace:
        return []
    user_id = user["user_id"]
    concepts_dir = get_concepts_dir(user_id, workspace)
    if not concepts_dir.exists():
        return []

    files = []
    try:
        for f in concepts_dir.glob("*.md"):
            if f.stem.lower() == "index":
                continue
            content = f.read_text(encoding="utf-8")
            if DRAFT_TAG not in content:
                continue
            stat = f.stat()
            clean = re.sub(r'<.*?AUTOFILL_DRAFT.*?>', '', content)
            clean = re.sub(r'[#*\[\]\n]', ' ', clean)[:40].strip()
            files.append({
                "id": f.stem,
                "title": f.stem,
                "excerpt": f"{clean}..." if clean else "无正文内容...",
                "timestamp": stat.st_mtime,
            })
        files.sort(key=lambda x: x["timestamp"], reverse=True)
        return files[:4]
    except Exception:
        return []


@app.post("/api/inbox/approve")
async def approve_inbox_file(workspace: str, file_id: str, user=Depends(get_current_user)):
    user_id = user["user_id"]
    filepath = get_concepts_dir(user_id, workspace) / f"{file_id}.md"
    if filepath.exists():
        content = filepath.read_text(encoding="utf-8")
        content = content.replace(DRAFT_TAG + "\n", "").replace(DRAFT_TAG, "")
        filepath.write_text(content, encoding="utf-8")
    return {"status": "success"}


# ==========================================
# 📡 7. 需求雷达 (Radar)
# ==========================================
@app.get("/api/radar")
async def get_radar(workspace: str, user=Depends(get_current_user)):
    if not workspace:
        return []
    user_id = user["user_id"]
    concepts_dir = get_concepts_dir(user_id, workspace)
    if not concepts_dir.exists():
        return []

    from collections import Counter
    existing_files = list(concepts_dir.glob("*.md"))
    link_counter = Counter()

    try:
        for fp in existing_files:
            content = fp.read_text(encoding="utf-8")
            for link in re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content):
                clean = link.strip()
                if clean:
                    link_counter[clean] += 1

        def _get_real_target(ghost: str, files: list) -> str:
            def _aliases(text: str) -> set:
                a = set()
                c = text.lower().replace("-", "").replace("_", "").replace(" ", "")
                if c:
                    a.add(c)
                m = re.match(r'^(.*?)\s*[\(（](.*?)[\)）]', text)
                if m:
                    for p in [m.group(1), m.group(2)]:
                        p = p.lower().replace("-", "").replace("_", "").replace(" ", "")
                        if p:
                            a.add(p)
                return a

            ga = _aliases(ghost)
            for f in files:
                if ga & _aliases(f.stem):
                    return f.stem
            return ""

        ghosts = []
        for link, count in link_counter.items():
            real = _get_real_target(link, existing_files)
            if not real and link.lower() != "index" and count >= 1:
                ghosts.append((link, count))
        ghosts.sort(key=lambda x: x[1], reverse=True)

        return [
            {"concept": name, "urgency": min(100, count * 12), "mentions": count}
            for name, count in ghosts[:5]
        ]
    except Exception:
        return []


# ==========================================
# ⚖️ 8. Inbox 物理审批 (CRUD)
# ==========================================
@app.get("/api/inbox/file")
async def get_inbox_file(workspace: str, file_id: str, user=Depends(get_current_user)):
    user_id = user["user_id"]
    filepath = get_concepts_dir(user_id, workspace) / f"{file_id}.md"
    if not filepath.exists():
        raise HTTPException(status_code=404)
    content = filepath.read_text(encoding="utf-8").replace(DRAFT_TAG + "\n", "")
    return {"content": content}


@app.post("/api/inbox/reject")
async def reject_inbox_file(workspace: str, file_id: str, user=Depends(get_current_user)):
    user_id = user["user_id"]
    filepath = get_concepts_dir(user_id, workspace) / f"{file_id}.md"
    if filepath.exists():
        filepath.unlink()
    return {"status": "success"}


# ==========================================
# 📊 9. 报告生成 (Stage 3)
# ==========================================
@app.post("/api/report")
async def report_endpoint(request: ReportRequest, user=Depends(get_current_user)):
    user_id = user["user_id"]
    if not request.workspace:
        raise HTTPException(status_code=400, detail="必须指定工作区")

    from workflows.report_flow import ReportFlow
    rf = ReportFlow(user_id=user_id)
    session_id = request.session_id or f"{user_id}:{request.workspace}:report"

    return StreamingResponse(
        rf.generate(
            topic=request.topic,
            workspace=request.workspace,
            outline=request.outline or "",
            session_id=session_id,
        ),
        media_type="text/event-stream",
    )


# ==========================================
# 🌐 SPA 前端入口 (Vite 开发代理或静态文件)
# ==========================================
from starlette.responses import FileResponse, RedirectResponse
from starlette.staticfiles import StaticFiles

DIST_DIR = PROJECT_ROOT / "web" / "dist"

if DIST_DIR.exists():
    # 生产模式：挂载静态文件
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="static_assets")

    @app.get("/")
    async def spa_index_prod():
        return FileResponse(str(DIST_DIR / "index.html"))

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """SPA 路由回退"""
        file_path = DIST_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(DIST_DIR / "index.html"))
else:
    @app.get("/")
    async def spa_index_dev():
        return RedirectResponse(url="http://localhost:3000")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)