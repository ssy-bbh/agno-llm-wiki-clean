# LLM Wiki Project

> 基于 Agno 框架的多智能体知识研究系统，核心理念：**让大模型像维护维基百科一样持续管理你的私人知识库**。

---

## 📁 目录结构

```
agno-llm-wiki-demo/
│
├── .env                    # 环境变量（Qwen API Key 等）
├── requirements.txt        # 项目依赖
├── app.py                  # 中枢总控台（FastAPI + AgentOS）
│
├── core/                   # ① 核心基座层（原有，维持不动）
│   ├── config.py           # 读取 .env，全局配置
│   ├── llm_factory.py      # 模型工厂：Qwen-Max / Qwen-VL
│   └── memory_manager.py   # SQLite 会话记忆 + LanceDB 向量存储
│
├── protocols/              # ② 维基协议层（【新增】）
│   ├── purpose.md          # 知识库灵魂：使命边界、意图、核心论点
│   └── schema.md           # 操作 SOP：双链语法、页面结构、降级策略
│
├── tools/                  # ③ 技能工具箱
│   ├── search_tools.py     # DuckDuckGo 联网搜索 ✅
│   ├── ppt_tools.py        # python-pptx 封装（扩展中）🔧
│   ├── vision_tools.py     # 图片/OCR 封装（扩展中）🔧
│   ├── file_tools.py       # 读写隔离：权限圈禁在 data/wiki/ 内 ✅
│   └── edit_tools.py       # str_replace 精密替换，防止格式错乱 ✅
│
├── prompts/                # ④ 提示词工程库
│   ├── boss_prompt.py      # 主管 Agent 路由规则
│   ├── research_prompt.py  # 深度研究协议
│   └── wiki_prompt.py      # Wiki 维护者角色定义 ✅
│
├── agents/                 # ⑤ 原子智能体
│   ├── web_researcher.py   # 联网研究员 ✅
│   ├── local_wiki.py       # 本地知识库（向量检索）✅
│   ├── wiki_analyst.py     # 知识分析师：只读不做写 ✅
│   └── wiki_writer.py      # 知识撰稿人：只写不分析 ✅
│
├── workflows/              # ⑥ 确定性工作流层（【新增】）
│   ├── __init__.py
│   ├── ingest_flow.py      # 摄入流水线（Analyze→Write，严格串行）✅
│   └── lint_flow.py        # 审查流水线（死链/孤立页面清理）✅
│
├── data/                   # ⑦ 数据层（【重构】读写分离）
│   ├── raw/               # 来源只读层：PDF、图片等原始资料
│   └── wiki/              # 维基编译层：大模型全权维护
│       ├── concepts/       # 知识概念节点页面
│       ├── entities/       # 具体人物/项目实体页面
│       ├── index.md        # 全局导航地图（每次读写必读）
│       └── log.md          # Append-only 审计日志
│
└── storage/                # ⑧ 记忆持久化（已加入 .gitignore）
    ├── sqlite/             # Agno SQLite 会话记忆
    └── lancedb/            # 向量数据库（长尾兜底检索）
```

---

## 🗺️ 架构设计核心逻辑

### 分离 Protocols 与 Prompts

```
Prompts (提示词)    → 怎么调用模型（语气、格式）
Protocols (协议)    → 怎么维护知识库（规范、语法）
```

将 `schema.md` / `purpose.md` 物理隔离，像改文档一样调整维基演进策略，无需动 Python 代码。

### 引入 Workflows（工作流）

摄入新知识时，**必须按确定性步骤执行**，禁止 Agent 自由发挥：

```
ingest_flow.py 流水线步骤：
  ① wiki_analyst   只读不写 → 输出分析报告（内存中碰撞新旧知识）
  ② wiki_writer    接收报告 → 调用 edit_tools 执行原子性写入
```

### 两步思维链（Two-Step CoT）

```
wiki_analyst  专注分析：找张力、找缺口、找关联
wiki_writer   专注写入：str_replace 精密替换，不全量覆写
```

### 底层 Data 拓扑

```
data/raw/    → 只读，大模型只能消费，不能写入
data/wiki/   → 大模型全权写入，index.md 是全局寻址核心
```

LanceDB 仅作为 `index.md` 超载时的语义兜底，不作为主存储。

---

## 🔧 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
# 编辑 .env：
QWEN_API_KEY=sk-xxxxxxxxxxxxxxxx

# 3. 上传原始资料
# 把 PDF、图片放入 data/raw/

# 4. 启动服务
python app.py

# 5. 执行首次摄入（Python 脚本）
from workflows import IngestFlow
flow = IngestFlow(source_file="my-paper.pdf", context="这是XXX论文")
result = flow.run()
print(result)
```

---

## 📋 TODO

### ✅ 已完成

- [x] 目录结构设计与搭建
- [x] `protocols/schema.md` — 维基操作 SOP
- [x] `protocols/purpose.md` — 知识库使命定义
- [x] `tools/file_tools.py` — 读写隔离文件工具
- [x] `tools/edit_tools.py` — str_replace 精密替换工具
- [x] `prompts/wiki_prompt.py` — Wiki 维护者角色提示词
- [x] `agents/wiki_analyst.py` — 知识分析师 Agent
- [x] `agents/wiki_writer.py` — 知识撰稿人 Agent
- [x] `workflows/ingest_flow.py` — 摄入流水线
- [x] `workflows/lint_flow.py` — 审查流水线
- [x] README.md 编写

### 🔧 扩展中

- [ ] `app.py` 接入新的 Wiki Agents 和 Workflows
- [ ] `tools/ppt_tools.py` — PPT 生成工具封装
- [ ] `agents/ppt_maker.py` — PPT 生成 Agent
- [ ] `prompts/ppt_prompt.py` — PPT 排版提示词

### 🐣 待开发

- [ ] `tools/vision_tools.py` — 图片读取 / OCR 工具
- [ ] `agents/vision_analyst.py` — 视觉分析师 Agent
- [ ] `agents/local_wiki.py` 与 LanceDB 的长尾兜底检索集成
- [ ] `app.py` 中 Wiki Agents 与现有 Web Researcher 的路由逻辑
- [ ] 增量摄入：同一来源文件的二次更新（diff + merge）
- [ ] 冲突解决：多个来源同时引用同一概念时的合并策略
- [ ] `lint_flow.py` 调用大模型自动修复死链（而非仅报告）
- [ ] `index.md` 超载时自动拆分（>500 行阈值）
- [ ] Web 前端：上传资料、查看摄入状态、浏览 Wiki 页面

### 📌 已知限制

- `edit_tools.py` 的 `str_replace` 依赖精确匹配空白符，需保证 old_str 完全一致
- `lint_flow.py` 目前只做静态扫描，不调用 LLM 修复；修复能力在 TODO 列表中
- PDF 读取依赖 `pdfplumber`，需 pip install

---

## 📦 主要依赖

```txt
agno>=1.0
openai
python-dotenv
duckduckgo-search
newspaper4k
lancedb
sqlalchemy
fastapi
uvicorn
pdfplumber          # PDF 解析
python-pptx          # PPT 生成（扩展中）
pillow              # 图片处理（扩展中）
```
