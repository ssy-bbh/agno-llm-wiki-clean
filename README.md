# LLM Wiki Demo — 多智能体知识研究系统

> 基于 Agno 框架的多智能体系统——让大模型像维护维基百科一样持续管理你的私人知识库。

---

## 项目概述

**LLM Wiki Demo** 是一个基于 Agno 框架构建的多智能体知识研究系统。核心理念是：**让 LLM 像维护维基百科一样，持续自动管理你的私人知识库**。

知识库不是静态文档，而是**活的系统**——自动摄入新资料、交叉验证多来源、发现概念关联、定期审查死链，像维基百科编辑团队一样 7×24 运转。

---

## 四大核心设计原则

### 1. Protocols 与 Prompts 分离

| 层 | 职责 | 修改方式 |
|---|---|---|
| **Protocols** (`protocols/`) | **做什么**——知识库使命边界、双链语法、页面模板、操作 SOP | 编辑 `.md` 文件，无需触碰 Python |
| **Prompts** (`prompts/`) | **怎么说**——模型语气、输出格式、角色设定 | 编辑 Python 字符串 |

像改文档一样调整策略，无需修改源码。

### 2. 分析师-主编-撰稿人 三级流水线 + 两步思维链

```
新资料 ──▶ wiki_analyst ──▶ AnalysisReport ──▶ wiki_editor ──▶ EditorReport ──▶ wiki_writer ──▶ data/wiki/
  (原始输入)    (只读分析)    (概念+摘要)        (比对决策)     (精确动作)      (只写执行)      (str_replace)
```

- **分析师**（`wiki_analyst`）：纯文本推理，提取核心概念与摘要，输出 `AnalysisReport`
- **主编**（`wiki_editor`）：检索已有知识，对比新旧内容，输出精确的 `EditorReport`（create / edit / append_link）
- **撰稿人**（`wiki_writer`）：纯 Python 执行器，接收 Report 后操作文件系统
- 分析与执行分离、决策与写入分离，中间传递 Pydantic 结构化报告

### 3. 读写分离

```
data/raw/    → 只读来源层，大模型只能消费，不能写入
data/wiki/   → 维基编译层，大模型全权写入
LanceDB      → 语义兜底，仅在 index.md 超载时启用
```

- `file_tools` 路径锁死 `data/wiki/`，严格拒绝目录遍历
- `index.md` 是全局导航地图，每次读写**必读**
- `log.md` 是 append-only 审计日志

### 4. Map-Reduce 并发摄入 + Workflow 确定性

| 工作流 | 步骤 | 特点 |
|---|---|---|
| `ingest_flow` | MAP 并发提取 → SHUFFLE 概念聚类 → REDUCE 逐概念融合 | **Map-Reduce 并发**，12线程并行提取 |
| `lint_flow` | 死链检测 → Backlinks 织网 → 孤立页面报告 | 定期审查 |
| `query_flow` | Team[local_wiki + web_researcher] → Summarizer 汇总 | 查询路由 |
| `autofill_flow` | 扫描双链 → 探测真空节点 → 自动合成填充 | 知识黑洞自愈 |

`ingest_flow` 采用三阶段 Map-Reduce 架构：Phase 1 12线程并发提取 → Phase 2 同义词聚类 → Phase 3 逐概念融合写入，兼顾效率与质量。

---

## 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                     app.py (FastAPI)                     │
│              AgentOS · Router · SqliteDb                 │
└────────────┬──────────────────────────┬──────────────────┘
             │                          │
    ┌────────▼────────┐        ┌────────▼──────────┐
    │   Agents 层      │        │  Workflows 层      │
    │  web_researcher │        │  ingest_flow       │
    │  local_wiki     │        │  lint_flow         │
    │  wiki_analyst ◄─┼───────►│  query_flow        │
    │  wiki_writer    │  CoT   │  autofill_flow     │
    │  wiki_editor    │        │                    │
    │  ppt_maker      │        │                    │
    │  vision_analyst │        │                    │
    └────────┬────────┘        └───────────┬────────┘
             │                             │
    ┌────────▼─────────────────────────────▼───┐
    │           Tools & Protocols               │
    │  search / file / edit / ppt / vision      │
    │  purpose.md / schema.md (协议层)          │
    └────────────────────┬──────────────────────┘
                         │
              ┌──────────▼──────────┐
              │    Data 层           │
              │  raw/  (只读来源)    │
              │  wiki/ (编译输出)    │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │   Storage 层         │
              │  SQLite 会话记忆     │
              │  LanceDB 向量检索    │
              └─────────────────────┘
```

---

## 目录结构

```
agno-llm-wiki-demo/
├── .env                    # API Key 配置
├── requirements.txt        # 依赖
├── app.py                  # FastAPI + AgentOS 入口
│
├── core/                   # 核心基座层
│   ├── config.py           # pydantic Settings 全局配置
│   ├── llm_factory.py      # 模型工厂：Qwen-Max / Qwen-VL
│   └── memory_manager.py   # SQLite 会话记忆 + LanceDB 向量存储
│
├── protocols/              # 维基协议层
│   ├── purpose.md          # 知识库使命边界、核心论点
│   └── schema.md           # 操作SOP：双链语法、页面模板
│
├── tools/                  # 技能工具箱
│   ├── search_tools.py     # DuckDuckGo + Newspaper4k
│   ├── file_tools.py       # 读写隔离，路径锁在 data/wiki/
│   ├── edit_tools.py       # str_replace + create_page + append_to_log
│   ├── ppt_tools.py        # python-pptx 封装（扩展中）
│   └── vision_tools.py     # 图片/OCR（扩展中）
│
├── prompts/                # 提示词工程库
│   ├── boss_prompt.py      # 主管路由：Research / Wiki / PPT
│   ├── research_prompt.py  # 深度研究协议
│   ├── wiki_prompt.py      # Wiki维护者 + load_protocols()
│   └── ppt_prompt.py       # PPT排版指令
│
├── agents/                 # 原子智能体
│   ├── web_researcher.py   # 联网搜索
│   ├── local_wiki.py       # 本地知识库（LanceDB）
│   ├── wiki_analyst.py     # 只读分析，输出 AnalysisReport
│   ├── wiki_writer.py      # 只写执行：create/edit/append_link
│   ├── wiki_editor.py      # 比对新旧知识，生成 EditorReport
│   ├── ppt_maker.py        # PPT生成（扩展中）
│   └── vision_analyst.py   # 视觉分析（扩展中）
│
├── workflows/              # 确定性工作流
│   ├── ingest_flow.py      # 摄入流水线：Map-Reduce 三阶段并发
│   ├── lint_flow.py        # 审查流水线：死链检测 + 反向链接织网
│   ├── query_flow.py       # 查询路由：Team[local_wiki+web_researcher]→汇总
│   └── autofill_flow.py    # 幽灵节点填补：探测真空节点并自动合成
│
├── data/                   # 数据层（读写分离）
│   ├── raw/               # 只读来源层
│   └── wiki/              # 维基编译层（LLM全权写入）
│       ├── concepts/      # 概念页面
│       ├── entities/      # 实体页面
│       ├── index.md       # 全局导航地图
│       └── log.md         # Append-only审计日志
│
└── storage/                # 记忆持久化（.gitignore）
    ├── sqlite/            # 会话记忆
    └── lancedb/           # 向量索引
```

---

## 入口文件

```python
from agno.os import AgentOS
from agents.local_wiki import get_local_wiki
from workflows.query_flow import get_query_workflow

wiki_expert = get_local_wiki()
router_workflow = get_query_workflow()

agent_os = AgentOS(
    agents=[],
    workflows=[router_workflow],
    db=SqliteDb(db_file="tmp/agent_os.db"),
    tracing=True
)
```

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API Key（编辑 .env）
QWEN_API_KEY=sk-xxxxxxxxxxxxxxxx

# 3. 上传原始资料
# 将 PDF / 图片 / 文档放入 data/raw/

# 4. 启动服务
python app.py

# 5. 查询知识库
from workflows.query_flow import get_query_workflow
wf = get_query_workflow()
result = wf.run(query="你的问题")
```

---

## 依赖

| 依赖 | 用途 |
|---|---|
| `agno>=1.0` | 多智能体编排框架 |
| `openai` | LLM API 客户端 |
| `python-dotenv` | 环境变量管理 |
| `duckduckgo-search` | 联网搜索 |
| `newspaper4k` | 网页正文提取 |
| `lancedb` | 向量数据库（长尾兜底） |
| `sqlalchemy` | ORM / SQLite 持久化 |
| `fastapi` | Web 框架 |
| `uvicorn` | ASGI 服务器 |
| `pdfplumber` | PDF 解析 |
| `python-pptx` | PPT 生成（扩展中） |
| `pillow` | 图像处理（扩展中） |

---

## TODO

### ✅ 已完成

- [x] 项目目录结构与基础框架
- [x] Protocols 协议层（purpose.md / schema.md）
- [x] Tools 工具箱（search / file / edit）
- [x] Prompts 提示词库（boss / research / wiki / ppt）
- [x] 核心 Agents（web_researcher / local_wiki / wiki_analyst / wiki_writer / wiki_editor）
- [x] Workflows（ingest_flow / lint_flow / query_flow）
- [x] 读写分离数据拓扑 + index.md 全局导航
- [x] LanceDB 向量兜底检索
- [x] 两步思维链（分析师→主编→撰稿人三级流水线）
- [x] Map-Reduce 并发摄入引擎（12线程 + 同义词聚类 + 逐概念融合）
- [x] 幽灵节点自动填补（autofill_flow 双向链接扫描 + 真空合成）

### 🔧 扩展中

- [ ] app.py 完整接入 Wiki Agents 和 Workflows
- [ ] PPT 生成管线（ppt_tools / ppt_maker / ppt_prompt）
- [ ] 视觉分析管线（vision_tools / vision_analyst）

### 📌 规划中

- [ ] `index.md` 超载自动拆分（>500 行阈值）
- [ ] 增量摄入：同一来源二次更新（diff + merge）
- [ ] 冲突解决：多来源引用同一概念的合并策略
- [ ] 上下文智能剪枝：按标题分块 + 语义匹配，减少主编输入负载
- [ ] `lint_flow.py` LLM 自动修复死链（当前仅报告）
- [ ] Web 前端：资料上传 / 摄入状态 / Wiki 浏览

---


