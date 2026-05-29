# LLM Wiki Demo — 多智能体知识研究系统

> 基于 Agno 框架的多智能体系统——让大模型像维护维基百科一样持续管理你的私人知识库。

---

## 项目概述

**LLM Wiki Demo** 是一个基于 Agno 框架构建的多智能体知识研究系统。核心理念是：**让 LLM 像维护维基百科一样，持续自动管理你的私人知识库**。

知识库不是静态文档，而是**活的系统**——自动摄入新资料、交叉验证多来源、发现概念关联、定期审查死链，像维基百科编辑团队一样 7×24 运转。

---

## 五大核心设计原则

### 1. Protocols 与 Prompts 分离

| 层 | 职责 | 修改方式 |
|---|---|---|
| **Protocols** (`protocols/`) | **做什么**——知识库使命边界、双链语法、页面模板、操作 SOP | 编辑 `.md` 文件，无需触碰 Python |
| **Prompts** (各 Agent 内联) | **怎么说**——模型语气、输出格式、角色设定 | 编辑 Agent `.py` 中的 `instructions` 字符串 |

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

### 3. 读写分离 + 用户隔离

```
data/raw/{user_id}/    → 只读来源层，大模型只能消费，不能写入
data/wiki/{user_id}/   → 维基编译层，大模型全权写入（按用户物理隔离）
data/memory.db         → SQLite 会话记忆（Agno SqliteDb）
```

- `file_tools` 路径锁死 `data/wiki/`，严格拒绝目录遍历
- `path_resolver.py` 统一解析所有路径，确保用户只能访问自己的数据
- `index.md` 是全局导航地图，每次读写**必读**

### 4. 多 Worker 状态共享 + 实时进度可视化

服务器以 `uvicorn --workers N` 部署时，多个 Worker 进程内存互不共享。本项目采用**文件共享存储**（`data/.ingest_status/`）替代内存字典，实现：

- 摄入状态（`{user_id}__{workspace}.json`）跨 Worker 可见
- 结构化进度（`{user_id}__{workspace}_progress.json`）跨 Worker 可读
- 前端乐观更新 + 竞态保护（`optimisticUntilRef`）避免 poll 抖动

前端 CyberForge 组件将进度解析为 4 阶段可视化卡片：
```
📄 解析文档 → ⚡ 提取概念 → 🔀 聚类归并 → 🧠 融合落盘
```
每阶段显示百分比、文件名、概念计数、耗时计时器，SSE 实时推送。

### 5. Map-Reduce 并发摄入 + Workflow 确定性

| 工作流 | 步骤 | 特点 |
|---|---|---|
| `ingest_flow` | MAP 并发提取 → SHUFFLE 概念聚类 → REDUCE 逐概念融合 | **Map-Reduce 并发**，12线程并行提取 |
| `lint_flow` | 死链检测 → Backlinks 织网 → 孤立页面报告 | 定期审查 |
| `query_flow` | Team[local_wiki + web_researcher] → Summarizer 汇总 | 查询路由 |
| `autofill_flow` | 扫描双链 → 探测真空节点 → 自动合成填充 | 知识黑洞自愈 |
| `report_flow` | TopicScanner → BulkRetriever → ReportSynthesizer | 批量报告生成 |

`ingest_flow` 采用三阶段 Map-Reduce 架构：Phase 1 12线程并发提取 → Phase 2 同义词聚类 → Phase 3 逐概念融合写入，兼顾效率与质量。

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│                        app.py (FastAPI)                           │
│          JWT Auth · IntentRouter · SSE Streaming                  │
└────────────┬───────────────────────────────────────┬──────────────┘
             │                                       │
    ┌────────▼────────┐                   ┌──────────▼──────────┐
    │   core/ 基座层    │                   │   Workflows 层       │
    │  auth.py (JWT)   │                   │  ingest_flow        │
    │  path_resolver   │                   │  lint_flow          │
    │  model_router    │                   │  query_flow         │
    │  task_log(进度)  │                   │  autofill_flow      │
    │  llm_factory     │                   │  report_flow        │
    └────────┬────────┘                   └──────────┬──────────┘
             │                                       │
    ┌────────▼────────┐                   ┌──────────▼──────────┐
    │   Agents 层      │                   │  Tools & Protocols  │
    │  web_researcher │◀──────CoT────────▶│  edit / search /    │
    │  local_wiki     │                   │  file / document    │
    │  wiki_analyst   │                   │  ppt / vision       │
    │  wiki_writer    │                   │                     │
    │  wiki_editor    │                   │  purpose.md         │
    │  wiki_query     │                   │  schema.md          │
    └────────┬────────┘                   └──────────┬──────────┘
             │                                       │
    ┌────────▼───────────────────────────────────────▼───┐
    │                    Data 层 (用户隔离)                │
    │  data/wiki/{user_id}/{workspace}/concepts/*.md     │
    │  data/raw/{user_id}/                               │
    │  data/memory.db (SQLite 会话记忆)                   │
    └────────────────────────────────────────────────────┘
```

---

## 目录结构

```
agno-llm-wiki-demo/
├── .env                    # API Key + 白名单 + 配置
├── .env.example            # 配置模板
├── requirements.txt        # 依赖（17 个包）
├── app.py                  # FastAPI 入口（JWT + SSE + 全部 API 端点）
│
├── core/                   # 核心基座层
│   ├── auth.py             # JWT 认证、注册、白名单、角色管理
│   ├── config.py           # pydantic Settings 全局配置
│   ├── llm_factory.py      # 模型工厂：OpenAILike + Qwen
│   ├── model_router.py     # 多供应商 LLM 路由（BYOK）
│   ├── path_resolver.py    # 统一路径解析（用户隔离）
│   └── task_log.py         # 任务日志（环形缓冲 + 结构化进度 + 文件共享 + SSE 推送）
│
├── protocols/              # 维基协议层
│   ├── purpose.md          # 知识库使命边界、核心论点
│   └── schema.md           # 操作SOP：双链语法、页面模板
│
├── tools/                  # 技能工具箱
│   ├── search_tools.py     # DuckDuckGo + Newspaper4k
│   ├── file_tools.py       # 读写隔离，路径锁在 data/wiki/
│   ├── edit_tools.py       # str_replace + create_page + threading.local() 上下文
│   ├── document_parser.py  # PDF 解析（pdfplumber）+ 文本分块
│   ├── ppt_tools.py        # python-pptx 封装（扩展中）
│   └── vision_tools.py     # 图片/OCR（扩展中）
│
├── agents/                 # 原子智能体
│   ├── web_researcher.py   # 联网搜索
│   ├── local_wiki.py       # 本地知识库查询
│   ├── wiki_analyst.py     # 只读分析，输出 AnalysisReport
│   ├── wiki_writer.py      # 只写执行：create/edit/append_link
│   ├── wiki_editor.py      # 比对新旧知识，生成 EditorReport
│   ├── wiki_query.py       # 查询路由决策（WikiRouter）
│   ├── ppt_maker.py        # PPT生成（扩展中）
│   └── vision_analyst.py   # 视觉分析（扩展中）
│
├── workflows/              # 确定性工作流
│   ├── ingest_flow.py      # 摄入：Map-Reduce 三阶段并发
│   ├── lint_flow.py        # 审查：死链检测 + 反向链接织网
│   ├── query_flow.py       # 查询：Team[local_wiki+web_researcher]→汇总
│   ├── autofill_flow.py    # 幽灵节点填补：探测真空节点并自动合成
│   └── report_flow.py      # 报告生成：TopicScanner→BulkRetriever→ReportSynthesizer
│
├── data/                   # 数据层（读写分离 + 用户隔离）
│   ├── raw/{user_id}/     # 只读来源层（按用户隔离）
│   ├── wiki/{user_id}/    # 维基编译层（按用户隔离）
│   │   └── {workspace}/   # 沙箱
│   │       ├── concepts/  # 概念页面
│   │       └── index.md   # 导航地图
│   ├── .ingest_status/    # 跨 Worker 共享状态文件（自动生成）
│   └── memory.db          # SQLite 会话记忆
│
├── web/                   # Web 前端（React + Vite + Tailwind）
│   ├── src/
│   │   ├── components/    # UI 组件（14 个）
│   │   ├── contexts/      # React Context（AuthContext）
│   │   ├── data/          # Mock 数据
│   │   └── App.jsx        # 路由入口
│   └── dist/              # 生产构建产物（由 app.py 静态服务）
│
└── storage/                # 记忆持久化（.gitignore）
    ├── sqlite/
    └── lancedb/
```

---

## 快速开始

### 后端启动

```bash
# 1. 安装 Python 依赖（需要 Python 3.11+）
pip install -r requirements.txt

# 2. 配置环境变量（复制模板并编辑）
cp .env.example .env
# 编辑 .env：填入 QWEN_API_KEY、ALLOWED_USERS 等

# 3. 启动后端服务（生产模式，自带静态文件服务）
python app.py
# 后端监听 http://localhost:8888
```

### 前端开发（可选，生产环境直接用后端静态服务）

```bash
cd web
npm install
npm run dev      # 开发服务器 → http://localhost:5173（自动代理到 8888）
npm run build    # 构建生产包到 web/dist/
```

### 访问

- **生产模式**：直接访问 `http://localhost:8888`（后端服务前端静态文件 + SPA 回退）
- **开发模式**：访问 `http://localhost:5173`（Vite 热更新 + 代理 API 到 8888）

### 生产部署（Linux 服务器）

```bash
# 1. 上传源码到服务器（排除 .venv/node_modules/data/raw）
scp -r . root@<server>:/opt/llm-wiki-os/

# 2. 创建虚拟环境 + 安装依赖
cd /opt/llm-wiki-os
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd web && npm install && npm run build && cd ..

# 3. 配置 .env
cp .env.example .env && nano .env

# 4. 创建 systemd 服务
cat > /etc/systemd/system/llm-wiki.service << 'EOF'
[Unit]
Description=LLM-Wiki OS API Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/llm-wiki-os
Environment=PYTHONUNBUFFERED=1
Environment=PATH=/opt/llm-wiki-os/.venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/opt/llm-wiki-os/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8888 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now llm-wiki
```

> **注意**：`--workers N` 开启多进程时，摄入状态通过文件共享（`data/.ingest_status/`），无需额外配置。

---

## API 端点一览

| 分类 | 端点 | 方法 | 说明 |
|------|------|------|------|
| **认证** | `/api/auth/register` | POST | 注册（白名单控制） |
| | `/api/auth/login` | POST | 登录，返回 JWT Token |
| | `/api/auth/me` | GET | 当前用户信息 |
| **会话** | `/api/sessions` | GET | 会话列表 |
| | `/api/sessions/create` | POST | 创建会话 |
| | `/api/sessions/{id}` | DELETE | 删除会话 |
| | `/api/sessions/{id}/messages` | GET | 读取会话历史消息 |
| **知识库** | `/api/workspaces` | GET | 沙箱列表 |
| | `/api/workspaces/create` | POST | 创建沙箱 |
| | `/api/upload` | POST | 上传文件并触发摄入 |
| | `/api/graph` | GET | 力导向图数据 |
| | `/api/concept` | GET | 读取概念 Markdown 内容 |
| | `/api/inbox` | GET | 隔离审批区 |
| | `/api/inbox/approve` | POST | 批准草稿 |
| | `/api/inbox/reject` | POST | 拒绝草稿 |
| | `/api/radar` | GET | 需求雷达 |
| **对话** | `/api/chat` | POST | SSE 流式对话（意图路由） |
| | `/api/forge` | POST | 触发 lint/autofill |
| | `/api/report` | POST | 批量报告生成 |
| **设置** | `/api/settings/providers` | GET | 可用 LLM 供应商列表 |
| | `/api/settings/api-key` | POST | 保存用户 API Key |
| **任务日志** | `/api/task-logs/{ws}/stream` | GET | 用户任务日志 SSE 流（含进度事件） |
| | `/api/task-logs/{ws}/status` | GET | 摄入状态 + 结构化进度（跨 Worker 文件读取） |
| **管理** | `/api/admin/users` | GET | 用户列表（管理员） |
| | `/api/admin/sessions` | GET | 全局会话（管理员） |
| | `/api/admin/logs` | GET | 系统日志 SSE（管理员） |
| | `/api/admin/server-status` | GET | 服务器状态 |
| | `/api/admin/task-logs` | GET | 任务日志列表 |
| | `/api/admin/task-logs/{user}/{ws}` | GET/DELETE | 任务日志详情 |
| | `/api/admin/task-logs/{user}/{ws}/stream` | GET | 任务日志 SSE 流 |

---

## 授权声明

本项目**不附带任何开源许可证**。代码仅供个人研究与内部使用，未经作者明确书面授权，禁止以任何形式复制、分发、商用或用于训练。

## 依赖

| 依赖 | 用途 |
|---|---|
| `agno==2.5.17` | 多智能体编排框架 |
| `fastapi` | Web 框架 |
| `uvicorn` | ASGI 服务器 |
| `pydantic` / `pydantic-settings` | 数据验证 + 配置管理 |
| `PyJWT` | JWT Token 签发与验证 |
| `bcrypt` | 密码哈希 |
| `SQLAlchemy` | ORM / SQLite |
| `openai` | LLM API 客户端（OpenAILike 兼容） |
| `httpx` | HTTP 客户端 |
| `python-dotenv` | 环境变量管理 |
| `python-multipart` | 文件上传 |
| `pdfplumber` | PDF 解析 |
| `python-docx` | Word 文档解析 |
| `jinja2` | 模板引擎 |
| `requests` | HTTP 工具 |
| `starlette` / `anyio` | ASGI 基础 |

---

## TODO

### ✅ 已完成

- [x] 项目目录结构与基础框架
- [x] Protocols 协议层（purpose.md / schema.md）
- [x] Tools 工具箱（search / file / edit / document_parser）
- [x] 核心 Agents（web_researcher / local_wiki / wiki_analyst / wiki_writer / wiki_editor / wiki_query）
- [x] Workflows（ingest / lint / query / autofill / report）
- [x] 读写分离数据拓扑 + index.md 全局导航
- [x] 两步思维链（分析师→主编→撰稿人三级流水线）
- [x] Map-Reduce 并发摄入引擎（12线程 + 同义词聚类 + 逐概念融合）
- [x] 幽灵节点自动填补（autofill_flow）
- [x] **JWT 认证系统**（注册白名单、角色管理、Token 鉴权）
- [x] **用户级物理隔离**（`data/wiki/{user_id}/{workspace}/`）
- [x] **多轮会话记忆**（Agno SqliteDb + 会话历史 API）
- [x] **LLM 意图路由器**（IntentRouter Agent 替代正则启发式）
- [x] **并发安全**（threading.local() 替代 os.environ）
- [x] **Web 前端 SPA**（React + Tailwind + 力导向图 + KaTeX 数学渲染）
- [x] **管理员控制台**（用户管理、会话监控、任务日志 SSE、系统日志）
- [x] **批量报告生成**（report_flow：TopicScanner→BulkRetriever→ReportSynthesizer）
- [x] **BYOK 模型选择**（用户自带 API Key + 多供应商路由，管理员 fallback 系统 Key）
- [x] **可视化进度条**（CyberForge 4 阶段进度卡片，SSE 实时推送）
- [x] **多 Worker 状态共享**（文件替代内存字典，解决 uvicorn --workers N 状态隔离）
- [x] **对话错误气泡**（SSE error 事件 → 前端红色提示，替代静默失败）
- [x] **问候意图引导**（IntentRouter 识别 chat 意图 → 推送帮助 SSE 流）

### 🔧 扩展中

- [ ] PPT 生成管线（ppt_tools / ppt_maker）
- [ ] 视觉分析管线（vision_tools / vision_analyst）

### 📌 规划中

- [ ] `index.md` 超载自动拆分（>500 行阈值）
- [ ] 增量摄入：同一来源二次更新（diff + merge）
- [ ] 冲突解决：多来源引用同一概念的合并策略
- [ ] `lint_flow.py` LLM 自动修复死链（当前仅报告）
- [ ] XSS 防护（当前已用 react-markdown 替代 dangerouslySetInnerHTML）
- [ ] CORS 白名单 + 上传文件校验 + 速率限制
- [ ] 数据导出（Markdown ZIP / JSON）

---
