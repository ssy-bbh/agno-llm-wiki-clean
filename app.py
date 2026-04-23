# app.py
from agno.os import AgentOS
from agno.db.sqlite import SqliteDb

from agents.local_wiki import get_local_wiki
# 👇 导回我们的工作流
from workflows.query_flow import get_query_workflow

system_db = SqliteDb(db_file="tmp/agent_os.db")

wiki_expert = get_local_wiki()
#print("📚 正在扫描本地文献并构建 LanceDB 向量索引...")
#wiki_expert.knowledge.insert(path="data/raw")

# 👇 实例化标准的 Workflow
router_workflow = get_query_workflow()

agent_os = AgentOS(
    agents=[],
    workflows=[router_workflow],  # 👈 堂堂正正地挂在 workflows 列表里！
    db=system_db,
    tracing=True
)
app = agent_os.get_app()

if __name__ == "__main__":
    import uvicorn
    print("🚀 LLM Wiki 中枢已上线...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000,ws_ping_interval=15, reload=False)