import os
import sys
import re
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# 确保能正常加载同级及子目录模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from workflows.query_flow import QueryFlow

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


# 强健数据保安：严格对应前端载荷
class ChatRequest(BaseModel):
    query: str
    workspace: Optional[str] = ""
    history: List[Dict[str, Any]] = []


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


@app.get("/api/graph")
async def get_graph(workspace: str):
    """
    🎯 核心修复：精准定位 concepts 路径，通过正则提取真实 [[双链]] 拓扑
    """
    project_root = Path(__file__).resolve().parent
    base_dir = project_root / "data" / "wiki" / workspace

    # 💡 路径对齐：优先地毯式扫描 concepts 文件夹，若不存在则降级扫描工作区根目录
    concepts_dir = base_dir / "concepts"
    search_dir = concepts_dir if concepts_dir.exists() else base_dir

    if not base_dir.exists():
        return {"nodes": [], "links": []}

    nodes = []
    links = []
    node_set = set()

    try:
        # 1. 扫描所有真实的 .md 文件建立星图节点 (利用 rglob 递归向下抓取)
        for file_path in search_dir.rglob("*.md"):
            node_name = file_path.stem
            # 过滤导航索引文件，只保留真正的知识实体
            if node_name.lower() == "index":
                continue

            nodes.append({
                "id": node_name,
                "group": 1  # 默认分配基础青色，前端会根据此分类着色
            })
            node_set.add(node_name.lower())

        # 2. 核心算法：打开每个文件，用正则肉眼嗅探里面的 [[双链]] 建立真实连线
        for file_path in search_dir.rglob("*.md"):
            source_name = file_path.stem
            if source_name.lower() == "index":
                continue

            content = file_path.read_text(encoding="utf-8")
            # 完美匹配 [[概念名称]] 或带有别名的 [[概念名称|别名]] 语法
            matches = re.findall(r'\[\[(.*?)\]\]', content)

            for match in matches:
                # 如果带管道符 '|'，切分并剥离别名，只取前半段真实的物理文件名
                target_name = match.split("|")[0].strip()

                if target_name.lower() == "index":
                    continue

                # 🛡️ 严格安检：只有当目标节点在物理硬盘上确实存在时，才允许建立连线
                # 彻底拔除“幽灵连线”，防止前端 D3 物理引擎大爆炸黑屏！
                if target_name.lower() in node_set:
                    links.append({
                        "source": source_name,
                        "target": target_name
                    })

        return {"nodes": nodes, "links": links}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"星图拓扑解析失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)