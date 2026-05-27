import os
import sys
import re
import json
import threading
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# 确保能正常加载同级及子目录模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from workflows.query_flow import QueryFlow
from workflows.lint_flow import LintFlow
from workflows.autofill_flow import AutoFillFlow
from workflows.ingest_flow import IngestFlow

app = FastAPI(title="LLM-Wiki OS Backend", version="0.1.0")

# 允许跨域连接前端研发环境
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化核心工作流实例
query_flow = QueryFlow()
lint_flow = LintFlow()
autofill_flow = AutoFillFlow(threshold=5)  # 被引用 5 次即自动触发填补真空


# ==========================================
# 🧱 Pydantic 数据载荷安全防线
# ==========================================
class ChatRequest(BaseModel):
    query: str
    workspace: Optional[str] = ""
    history: List[Dict[str, Any]] = []
    intent_override: Optional[str] = None  # 前端可强制指定意图（调试用）


# ==========================================
# 🧠 轻量意图路由器 (极简 LLM Agent 一次调用)
# ==========================================
class Intent:
    CHAT    = "chat"      # 寒暄闲聊 → LLM 直接回复
    SCAN    = "scan"      # 扫描探索 → 列出 concepts 清单
    SUMMARY = "summary"   # 概览总结 → 读取 index.md 生成摘要
    QUERY   = "query"     # 具体知识查询 → 走完整 QueryFlow
    ERROR   = "error"     # 空输入 / 无效请求


from pydantic import BaseModel as _PydanticModel, Field as _Field
from typing import Literal as _Literal


class _IntentDecision(_PydanticModel):
    """意图分类器的结构化输出"""
    intent: _Literal["chat", "scan", "summary", "query"] = _Field(
        description="用户意图分类：chat(闲聊)/scan(扫描知识列表)/summary(知识库概览)/query(具体知识查询)"
    )


class IntentRouter:
    """极简意图路由 Agent —— 一次轻量 LLM 调用完成分类"""

    def __init__(self):
        from core.llm_factory import get_qwen_model
        from agno.agent import Agent

        self.agent = Agent(
            model=get_qwen_model(),
            instructions=[
                "你是一个意图分类器。根据用户的输入，判断其真实意图。"
                "只输出一个意图标签，不要解释。"
                "\n分类标准："
                "- chat：打招呼、问候、闲聊、夸赞 AI、问 AI 身份、简短回应（谢谢/好的/哈哈）"
                "- scan：询问知识库里有什么概念/节点/内容，要求列出清单、展示目录"
                "- summary：要求总结/概览/介绍整个知识库或某个沙箱的内容结构"
                "- query：提出具体的知识性问题，需要检索资料才能回答"
                "\n判定原则："
                "- 空输入直接返回 error"
                "- 不确定时优先 query（宁可多检索也不要误判）"
            ],
            output_schema=_IntentDecision,
            stream=False,
        )

    def classify(self, query: str) -> str:
        """分类用户意图，返回 intent 标签"""
        if not query or not query.strip():
            return Intent.ERROR

        q = query.strip()
        # 超短消息（≤3 字且不含标点/汉字），直接判定 chat
        import re
        if len(q) <= 3 and re.match(r'^[\s\u4e00-\u9fa5a-zA-Z]{1,3}$', q):
            return Intent.CHAT

        try:
            result = self.agent.run(q)
            if hasattr(result.content, 'model_dump'):
                return result.content.model_dump()['intent']
            if hasattr(result.content, 'intent'):
                return result.content.intent
            # fallback: 如果结构化解析失败，尝试从文本中提取
            text = str(result.content).lower()
            for tag in ['chat', 'scan', 'summary', 'query']:
                if tag in text:
                    return tag
        except Exception:
            pass

        return Intent.QUERY


# 全局单例（复用，避免重复创建 Agent）
_intent_router = None


def classify_intent(query: str) -> str:
    global _intent_router
    if _intent_router is None:
        _intent_router = IntentRouter()
    return _intent_router.classify(query)


class ForgeRequest(BaseModel):
    action: str  # "reweave" 或 "fill_blackhole"
    workspace: str


class SandboxCreate(BaseModel):
    name: str


# ==========================================
# 🗣️ 1. 探求模式接口 (Query Mode) — 五向意图路由
# ==========================================
@app.get("/api/intent/debug")
async def debug_intent(query: str):
    """调试端点：查看意图分类结果（不执行实际操作）"""
    return {"intent": classify_intent(query), "query": query}


@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """流式应答中枢 — 五向意图分发器 (chat / scan / summary / query / error)"""
    try:
        query = request.query.strip()
        workspace = request.workspace

        # 前端可强制覆盖意图（调试用）
        if request.intent_override and request.intent_override in (
            Intent.CHAT, Intent.SCAN, Intent.SUMMARY, Intent.QUERY
        ):
            intent = request.intent_override
        else:
            intent = classify_intent(query)

        print(f"🧠 [意图路由] '{query[:40]}' -> {intent}")

        # ─── 分轨处理 ───

        if intent == Intent.ERROR:
            # 🛤️ 轨道 0：空请求
            async def error_stream():
                yield f"data: {json.dumps({'type': 'text', 'content': '⚠️ 请输入你的问题或指令。'})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return StreamingResponse(error_stream(), media_type="text/event-stream")

        if intent == Intent.CHAT:
            # 🛤️ 轨道 A：闲聊模式 → 直接回复，不调检索管线
            return StreamingResponse(
                _stream_chat_reply(query, history=request.history),
                media_type="text/event-stream"
            )

        if intent == Intent.SCAN:
            # 🛤️ 轨道 B：扫描模式 → 列出 concepts 清单
            return StreamingResponse(
                _stream_scan_response(query, workspace),
                media_type="text/event-stream"
            )

        if intent == Intent.SUMMARY:
            # 🛤️ 轨道 C：概览模式 → 读取 index.md 生成总结
            return StreamingResponse(
                _stream_summary_response(query, workspace),
                media_type="text/event-stream"
            )

        # 🛤️ 轨道 D：QUERY 模式 (默认) → 走完整 QueryFlow 检索管线
        return StreamingResponse(
            query_flow.stream_execute(
                user_question=query,
                target_workspace=workspace,
                history=request.history
            ),
            media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
#  意图分轨处理函数
# ==========================================

async def _stream_chat_reply(query: str, history: list = None):
    """闲聊轨道：直接让 LLM 以赛博朋克口吻回复，不检索知识库"""
    from core.llm_factory import get_qwen_model
    from agno.agent import Agent

    agent = Agent(
        model=get_qwen_model(),
        instructions=[
            "你是一个 AI 向导，回答简短、有趣、有个性。"
            "不要调用任何外部工具或知识库，直接基于你的常识回复。"
            "回复控制在 100 字以内。"
        ],
        stream=True,
    )

    # 拼装上下文
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


def _get_all_workspaces() -> list:
    """列出所有沙箱名，按 mtime 倒序"""
    wiki_base = Path(__file__).resolve().parent / "data" / "wiki"
    if not wiki_base.exists():
        return []
    workspaces = [d for d in wiki_base.iterdir() if d.is_dir()]
    workspaces.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return [w.name for w in workspaces]


def _get_default_workspace() -> str:
    """自动选取默认工作区（最新修改的那个）"""
    all_ws = _get_all_workspaces()
    return all_ws[0] if all_ws else ""


async def _stream_scan_response(query: str, workspace: str):
    """扫描轨道：未指定沙箱 → 全局扫描所有沙箱；指定了 → 只扫该沙箱"""
    import asyncio
    from pathlib import Path

    wiki_base = Path(__file__).resolve().parent / "data" / "wiki"

    # ── 未指定沙箱：全局概览（只展示沙箱名 + 节点数，不展开具体节点） ──
    if not workspace or not workspace.strip():
        all_ws = _get_all_workspaces()
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
            concepts_dir = wiki_base / ws_name / "concepts"
            count = 0
            if concepts_dir.exists():
                count = len([f for f in concepts_dir.glob("*.md") if f.stem.lower() != "index"])
            total_nodes += count
            ws_stats.append((ws_name, count))

        # 构建简洁概览
        lines = [f"📡 全局扫描完毕，共检测到 **{len(all_ws)}** 个沙箱 / **{total_nodes}** 个知识节点：\n"]
        lines.append("| 沙箱 | 节点数 | 状态 |")
        lines.append("|------|--------|------|")
        for ws_name, count in ws_stats:
            status = "✅ 已激活" if count > 0 else "⭕ 虚空"
            lines.append(f"| {ws_name} | {count} | {status} |")

        lines.append("\n💡 在左侧切换沙箱隔离区可深入查看具体节点，或直接输入具体问题。")
        content = "\n".join(lines)

        chunk_size = 15
        for i in range(0, len(content), chunk_size):
            yield f"data: {json.dumps({'type': 'text', 'content': content[i:i+chunk_size]})}\n\n"
            await asyncio.sleep(0.02)

        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return

    # ── 指定了沙箱：只扫该沙箱 ──
    concepts_dir = Path(__file__).resolve().parent / "data" / "wiki" / workspace / "concepts"
    available = []
    if concepts_dir.exists():
        available = sorted(
            [f.stem for f in concepts_dir.glob("*.md") if f.stem.lower() != "index"]
        )

    if available:
        group_size = 8
        groups = [available[i:i + group_size] for i in range(0, len(available), group_size)]
        display_lines = [f"📡 扫描完毕，在沙箱 **{workspace}** 中检测到 **{len(available)}** 个已实例化的知识节点：\n"]
        for idx, group in enumerate(groups):
            display_lines.append(f"{' | '.join(f'`{c}`' for c in group)}")
        display_lines.append(f"\n💡 点击图谱上的节点，或直接在下方输入具体问题，即可深入探索。")
        content = "\n".join(display_lines)
    else:
        content = (f"🔭 扫描完毕：沙箱 **{workspace}** 中尚未生成任何知识节点。\n\n"
                   f"知识宇宙还是一片虚空 —— 试着拖拽一些原始资料到赛博熔炉中进行首次摄入吧！")

    yield f"data: {json.dumps({'type': 'log', 'content': f'📡 [扫描] 正在读取沙箱 [{workspace}] ...'})}\n\n"
    await asyncio.sleep(0.3)

    chunk_size = 15
    for i in range(0, len(content), chunk_size):
        chunk = content[i:i + chunk_size]
        yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"
        await asyncio.sleep(0.02)

    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def _stream_summary_response(query: str, workspace: str):
    """概览轨道：读取 index.md，让 LLM 生成知识库总结"""
    import asyncio
    from pathlib import Path
    from core.llm_factory import get_qwen_model
    from agno.agent import Agent

    # 沙箱未指定时自动兜底
    if not workspace or not workspace.strip():
        workspace = _get_default_workspace()
        if not workspace:
            content = "📋 系统中尚未创建任何知识沙箱，无法生成概览。"
            for i in range(0, len(content), 15):
                yield f"data: {json.dumps({'type': 'text', 'content': content[i:i+15]})}\n\n"
                await asyncio.sleep(0.02)
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

    index_path = Path(__file__).resolve().parent / "data" / "wiki" / workspace / "index.md"

    yield f"data: {json.dumps({'type': 'log', 'content': f'📋 [概览] 正在读取导航地图 ...'})}\n\n"
    await asyncio.sleep(0.3)

    if index_path.exists():
        index_content = index_path.read_text(encoding="utf-8")

        # 如果 index.md 很短（空知识库），直接回复
        if len(index_content.strip()) < 50:
            content = (f"📋 沙箱 **{workspace}** 的导航地图几乎空白。\n\n"
                       f"知识库尚未建立结构化的导航体系 —— 建议先进行知识摄入。")
            chunk_size = 15
            for i in range(0, len(content), chunk_size):
                yield f"data: {json.dumps({'type': 'text', 'content': content[i:i + chunk_size]})}\n\n"
                await asyncio.sleep(0.02)
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # 让 LLM 基于 index.md 生成总结
        agent = Agent(
            model=get_qwen_model(),
            instructions=[
                "你是一位知识库架构师。根据以下导航地图（index.md），用简洁、结构化的语言"
                "总结当前知识库的核心内容领域、覆盖范围和知识结构。"
                "回答控制在 200 字以内，使用 Markdown 格式。"
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
        content = (f"📋 沙箱 **{workspace}** 中尚未建立导航地图（index.md）。\n\n"
                   f"建议先摄入一些原始资料，让系统自动生成知识结构。")
        chunk_size = 15
        for i in range(0, len(content), chunk_size):
            yield f"data: {json.dumps({'type': 'text', 'content': content[i:i + chunk_size]})}\n\n"
            await asyncio.sleep(0.02)

    yield f"data: {json.dumps({'type': 'done'})}\n\n"

# ==========================================
# 🕸️ 2. 织网模式清洗调度流接口 (Forge Mode)
# ==========================================
@app.post("/api/forge")
async def forge_endpoint(request: ForgeRequest):
    """🕸️ 织网模式控制中枢：动态调度后端异步清洗引擎，向前端推流熔炉实时日志"""
    if not request.workspace:
        raise HTTPException(status_code=400, detail="必须指定具体的隔离沙箱才能启动织网熔炉！")

    async def run_forge_task():
        try:
            if request.action == "reweave":
                async for log in lint_flow.stream_run(request.workspace):
                    yield log
            elif request.action == "fill_blackhole":
                async for log in autofill_flow.stream_run(request.workspace):
                    yield log
            else:
                yield f"data: {json.dumps({'type': 'log', 'content': '❌ 拒绝执行：未知的织网运维指令。'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'log', 'content': f'💥 熔炉核心崩溃: {str(e)}'})}\n\n"

        # 释放结束信号
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(run_forge_task(), media_type="text/event-stream")


# ==========================================
# 🗂️ 3. 新建沙箱物理开荒接口 (Sandbox Create)
# ==========================================
@app.post("/api/workspaces/create")
async def create_workspace(req: SandboxCreate):
    """🗂️ 物理开荒：在 data/wiki/ 和 data/raw/ 下同时创建新的知识沙箱文件夹"""
    if not req.name:
        raise HTTPException(status_code=400, detail="沙箱名称不能为空！")

    # 严格过滤非法路径字符，防止路径穿越攻击
    safe_name = re.sub(r'[\\/*?:"<>|]', "", req.name).strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="非法的沙箱名称！")

    project_root = Path(__file__).resolve().parent
    wiki_dir = project_root / "data" / "wiki" / safe_name / "concepts"
    raw_dir = project_root / "data" / "raw" / safe_name

    try:
        wiki_dir.mkdir(parents=True, exist_ok=True)
        raw_dir.mkdir(parents=True, exist_ok=True)
        return {"status": "success", "workspace": safe_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"物理开荒失败: {str(e)}")


# ==========================================
# 📥 4. 原始语料多文件批量落盘摄入接口 (Batch Ingest)
# ==========================================
@app.post("/api/upload")
async def upload_batch_endpoint(workspace: str = Form(...), files: List[UploadFile] = File(...)):
    """📥 批量摄入流网关：接收多个原始语料，保存至对应沙箱目录，并后台排队批量摄入"""
    if not workspace:
        raise HTTPException(status_code=400, detail="必须指定目标沙箱！")
    if not files:
        raise HTTPException(status_code=400, detail="未检测到任何文件！")

    project_root = Path(__file__).resolve().parent
    raw_dir = project_root / "data" / "raw" / workspace
    raw_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    try:
        # 1. 极速前台落盘
        for file in files:
            file_path = raw_dir / file.filename
            contents = await file.read()
            file_path.write_bytes(contents)
            saved_paths.append(file_path)

        # 2. 开启后台守护线程：循环调度 IngestFlow 逐个炼丹，绝不卡死前端
        def run_background_batch():
            flow = IngestFlow()
            for fp in saved_paths:
                print(f"\n🚀 [后台任务] 正在排队提取语料: {fp.name} -> 目标沙箱: {workspace}")
                os.environ["ACTIVE_KB"] = workspace
                os.environ["ACTIVE_SUBDIR"] = ""
                os.environ["ACTIVE_DOC_NAME"] = fp.stem
                try:
                    flow.run(str(fp))
                except Exception as e:
                    print(f"❌ 提取 {fp.name} 失败: {e}")

            print(f"\n✅✅ 沙箱 [{workspace}] 的批量提炼任务已全部完成！")

        threading.Thread(target=run_background_batch).start()

        return {
            "status": "success",
            "message": f"成功落盘 {len(files)} 个文件",
            "files": [f.filename for f in files]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件批量落盘失败: {str(e)}")


# ==========================================
# 🔍 5. 基础拉取接口 (Workspaces & Graph)
# ==========================================
@app.get("/api/workspaces")
async def get_workspaces():
    """扫描本地 data/wiki 文件夹，向侧边栏喂入最真实的沙箱列表"""
    base_dir = os.path.join(os.path.dirname(__file__), "data", "wiki")
    if not os.path.exists(base_dir):
        return []
    try:
        return [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 📥 6. 隔离审批区接口 (Inbox)
# ==========================================
@app.get("/api/inbox")
async def get_inbox(workspace: str):
    """只扫描带有草稿烙印的待审实体"""
    if not workspace: return []
    concepts_dir = Path(__file__).resolve().parent / "data" / "wiki" / workspace / "concepts"
    if not concepts_dir.exists(): return []

    # 💡 组装安全烙印，防止前端意外吞噬
    DRAFT_TAG = "<" + "!-- AUTOFILL_DRAFT --" + ">"

    files = []
    try:
        for f in concepts_dir.glob("*.md"):
            if f.stem.lower() == "index": continue

            content = f.read_text(encoding="utf-8")
            # 💡 核心拦截：如果没有草稿烙印，直接跳过
            if DRAFT_TAG not in content:
                continue

            stat = f.stat()
            # 截取内容时，剔除烙印
            clean_excerpt = re.sub(r'<.*?AUTOFILL_DRAFT.*?>', '', content)
            clean_excerpt = re.sub(r'[#*\[\]\n]', ' ', clean_excerpt)[:40].strip()

            files.append({
                "id": f.stem,
                "title": f.stem,
                "excerpt": f"{clean_excerpt}..." if clean_excerpt else "无正文内容...",
                "timestamp": stat.st_mtime
            })

        files.sort(key=lambda x: x["timestamp"], reverse=True)
        return files[:4]
    except Exception as e:
        return []


@app.post("/api/inbox/approve")
async def approve_inbox_file(workspace: str, file_id: str):
    """静默放行：物理撕毁文件中的草稿烙印"""
    DRAFT_TAG_LINE = "<" + "!-- AUTOFILL_DRAFT --" + ">\n"
    DRAFT_TAG_INLINE = "<" + "!-- AUTOFILL_DRAFT --" + ">"

    filepath = Path(__file__).resolve().parent / "data" / "wiki" / workspace / "concepts" / f"{file_id}.md"
    if filepath.exists():
        content = filepath.read_text(encoding="utf-8")
        clean_content = content.replace(DRAFT_TAG_LINE, "").replace(DRAFT_TAG_INLINE, "")
        filepath.write_text(clean_content, encoding="utf-8")
    return {"status": "success"}


# ==========================================
# 📡 7. 需求雷达接口 (Radar) - 正式版 (5次60分)
# ==========================================
@app.get("/api/radar")
async def get_radar(workspace: str):
    if not workspace: return []

    from pathlib import Path
    import re
    from collections import Counter

    concepts_dir = Path(__file__).resolve().parent / "data" / "wiki" / workspace / "concepts"
    if not concepts_dir.exists():
        return []

    existing_files = list(concepts_dir.glob("*.md"))
    link_counter = Counter()

    try:
        # 1. 全局扫描提取引力链接
        for file_path in existing_files:
            content = file_path.read_text(encoding="utf-8")
            links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)

            for link in links:
                clean_link = link.strip()
                if not clean_link: continue
                link_counter[clean_link] += 1

        # 2. 精确别名解构，识别假死链
        def _get_real_target_if_exists(ghost_name: str, files: list) -> str:
            def _get_aliases(text: str) -> set:
                aliases = set()
                clean_text = text.lower().replace("-", "").replace("_", "").replace(" ", "")
                if clean_text: aliases.add(clean_text)
                match = re.match(r'^(.*?)\s*[\(（](.*?)[\)）]', text)
                if match:
                    part1 = match.group(1).lower().replace("-", "").replace("_", "").replace(" ", "")
                    part2 = match.group(2).lower().replace("-", "").replace("_", "").replace(" ", "")
                    if part1: aliases.add(part1)
                    if part2: aliases.add(part2)
                return aliases

            ghost_aliases = _get_aliases(ghost_name)
            for ex_file in files:
                ex_aliases = _get_aliases(ex_file.stem)
                if ghost_aliases & ex_aliases:
                    return ex_file.stem
            return ""

        # 3. 统计并筛选黑洞节点 (>=1次即可上榜)
        target_ghosts = []
        for link, count in link_counter.items():
            real_target = _get_real_target_if_exists(link, existing_files)
            if not real_target and link.lower() != "index" and count >= 1:
                target_ghosts.append((link, count))

        target_ghosts.sort(key=lambda x: x[1], reverse=True)

        # 4. 计分并返回前端 (1次12分，5次60分触发红温，封顶100分)
        radar_data = []
        for name, count in target_ghosts[:5]:
            score = min(100, count * 12)
            radar_data.append({
                "concept": name,
                "urgency": score,
                "mentions": count
            })

        return radar_data
    except Exception:
        return []
@app.get("/api/graph")
async def get_graph(workspace: str):
    """精准定位 concepts 路径，通过正则提取真实 [[双链]] 拓扑"""
    project_root = Path(__file__).resolve().parent
    base_dir = project_root / "data" / "wiki" / workspace

    concepts_dir = base_dir / "concepts"
    search_dir = concepts_dir if concepts_dir.exists() else base_dir

    if not base_dir.exists():
        return {"nodes": [], "links": []}

    nodes = []
    links = []
    node_set = set()

    try:
        for file_path in search_dir.rglob("*.md"):
            node_name = file_path.stem
            if node_name.lower() == "index":
                continue
            nodes.append({"id": node_name, "group": 1})
            node_set.add(node_name.lower())

        for file_path in search_dir.rglob("*.md"):
            source_name = file_path.stem
            if source_name.lower() == "index":
                continue

            content = file_path.read_text(encoding="utf-8")
            matches = re.findall(r'\[\[(.*?)\]\]', content)

            for match in matches:
                target_name = match.split("|")[0].strip()
                if target_name.lower() == "index":
                    continue
                if target_name.lower() in node_set:
                    links.append({"source": source_name, "target": target_name})

        return {"nodes": nodes, "links": links}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"星图拓扑解析失败: {str(e)}")


# ==========================================
# ⚖️ 8. Inbox 物理审批流接口 (读取/覆写/销毁)
# ==========================================
class FileEditRequest(BaseModel):
    workspace: str
    file_id: str
    content: str


@app.get("/api/inbox/file")
async def get_inbox_file(workspace: str, file_id: str):
    DRAFT_TAG_LINE = "<" + "!-- AUTOFILL_DRAFT --" + ">\n"

    filepath = Path(__file__).resolve().parent / "data" / "wiki" / workspace / "concepts" / f"{file_id}.md"
    if not filepath.exists(): raise HTTPException(status_code=404)
    # 返回给前端编辑时，隐藏这个丑陋的烙印
    content = filepath.read_text(encoding="utf-8").replace(DRAFT_TAG_LINE, "")
    return {"content": content}


@app.put("/api/inbox/file")
async def update_inbox_file(req: FileEditRequest):
    """人工介入，覆写大模型草稿并正式落盘（同时撕毁烙印）"""
    DRAFT_TAG_LINE = "<" + "!-- AUTOFILL_DRAFT --" + ">\n"

    filepath = Path(__file__).resolve().parent / "data" / "wiki" / req.workspace / "concepts" / f"{req.file_id}.md"
    if not filepath.exists(): raise HTTPException(status_code=404)
    # 保存时确保不带草稿烙印
    clean_content = req.content.replace(DRAFT_TAG_LINE, "")
    filepath.write_text(clean_content, encoding="utf-8")
    return {"status": "success"}


@app.delete("/api/inbox/file")
async def delete_inbox_file(workspace: str, file_id: str):
    filepath = Path(__file__).resolve().parent / "data" / "wiki" / workspace / "concepts" / f"{file_id}.md"
    if filepath.exists():
        filepath.unlink()
        return {"status": "success"}
    raise HTTPException(status_code=404)


# ==========================================
# 📖 9. 物理节点读取接口 (Concept Viewer)
# ==========================================
@app.get("/api/concept")
async def get_concept(workspace: str, name: str):
    """用于星图二次点击时，读取并展示具体的 MD 物理文件内容"""
    if not workspace or not name:
        return {"content": "参数错误：沙箱或节点名称丢失"}

    from pathlib import Path

    # 拼装路径: data/wiki/沙箱名/concepts/节点名.md
    file_path = Path(__file__).resolve().parent / "data" / "wiki" / workspace / "concepts" / f"{name}.md"

    if file_path.exists():
        try:
            content = file_path.read_text(encoding="utf-8")
            return {"content": content}
        except Exception as e:
            return {"content": f"文件读取异常: {str(e)}"}
    else:
        return {"content": "⚠️ 该概念仅作为图谱中的【黑洞引用】存在，尚未被大模型实例化生成物理文件。"}

if __name__ == "__main__":
    import uvicorn

    # 启动命令，热重载开启
    uvicorn.run("app:app", host="127.0.0.1", port=8888, reload=True)