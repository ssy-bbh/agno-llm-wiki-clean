# Agents — 多智能体系统

基于 **Agno** 框架的多智能体 Wiki 知识库构建系统。每个 Agent 各司其职，通过结构化中间产物（Pydantic Reports）协作，实现知识摄取、分析、融合的自动化流水线。

## Agent 一览

| Agent | 模型 | 工具 | 职责 | 状态 |
|---|---|---|---|---|
| `web_researcher.py` | Qwen-Max (`get_qwen_model()`) | DuckDuckGo + Newspaper4k | 全网深度搜索与网页内容抓取 | ✅ |
| `local_wiki.py` | Qwen-Max (`get_qwen_model()`) | LanceDB 知识库 | 本地知识库只读查询 | ✅ |
| `wiki_analyst.py` | Qwen-Max | 无（纯文本分析） | **只读分析**：从资料提取概念，输出 `AnalysisReport` | ✅ |
| `wiki_writer.py` | 无（纯执行器） | `edit_tools` | **只写执行**：接收报告，执行 create/edit/append_link/extract_moc | ✅ |
| `wiki_editor.py` | Qwen-Max | 无（纯决策） | **主编**：比对新旧知识，输出 `EditorReport` 融合动作 | ✅ |
| `ppt_maker.py` | — | `ppt_tools` | PPT 生成 | 🔧 WIP |
| `vision_analyst.py` | — | `vision_tools` | 视觉分析 | 🔧 WIP |

## 核心架构：两步思维链 (Two-Step CoT)

```
wiki_analyst (只读分析) ──AnalysisReport──▶ wiki_writer (只写执行)
        │                                      │
   分析新资料                              操作磁盘文件
   提取概念                                create_page / str_replace
   输出 AnalysisReport                     append_link / extract_moc
```

**为什么分两步？**
1. **分析阶段**（`wiki_analyst`）：纯文本推理，不碰磁盘。专注理解资料、提取概念、建立关联。
2. **执行阶段**（`wiki_writer`）：纯 Python 执行器，不做分析。接收 `AnalysisReport` 后直接调用 `edit_tools` 操作文件系统。

## 分析师-主编-撰稿人 三级流水线

完整的知识摄取链路：

```
新资料 ──▶ wiki_analyst ──▶ AnalysisReport ──▶ wiki_editor ──▶ EditorReport ──▶ wiki_writer ──▶ Wiki Pages
```

1. **分析师**（`wiki_analyst`）：从新资料提取概念，输出 `AnalysisReport`（不碰磁盘）
2. **主编**（`wiki_editor`）：调用 `local_wiki` 检索已有知识，对比新旧内容，生成精确的 `EditorReport` 融合动作
3. **撰稿人**（`wiki_writer`）：执行 `EditorReport` 中的 create / edit / append / link 操作

**分层设计原则**：

| 层 | 职责 | Agent | 特征 |
|---|---|---|---|
| **数据层** | 获取原始资料 | `web_researcher`, `local_wiki` | 外部输入 |
| **分析层** | 提取结构化知识 | `wiki_analyst` | 只读不写，输出 Pydantic |
| **决策层** | 融合新旧知识 | `wiki_editor` | 只读决策，输出 Pydantic |
| **执行层** | 持久化到磁盘 | `wiki_writer` | 只写不分析，纯执行器 |

## 关键文件

| 路径 | 说明 |
|---|---|
| `core/llm_factory.py` | 模型工厂，`get_qwen_model()` 统一提供 LLM 实例 |
| `prompts/wiki_prompt.py` | `build_analyst_system_prompt()` / `build_writer_system_prompt()` |
| `tools/edit_tools.py` | Wiki 页面编辑工具集 |
| `workflows/ingest_flow.py` | 知识摄取流水线编排 |

> **设计哲学**：让每个 Agent 做好一件事，通过结构化的中间产物传递信息，而非直接操作共享状态。分析与执行分离，决策与写入分离。
