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


class ForgeRequest(BaseModel):
    action: str  # "reweave" 或 "fill_blackhole"
    workspace: str


class SandboxCreate(BaseModel):
    name: str


# ==========================================
# 🗣️ 1. 探求模式接口 (Query Mode)
# ==========================================
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """接通隔离沙箱与历史长河的流式应答中枢"""
    try:
        return StreamingResponse(
            query_flow.stream_execute(
                user_question=request.query,
                target_workspace=request.workspace,
                history=request.history
            ),
            media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
if __name__ == "__main__":
    import uvicorn

    # 启动命令，热重载开启
    uvicorn.run("app:app", host="127.0.0.1", port=8888, reload=True)