# agents/ — 原子智能体

> **你的打工人**。每个 Agent = 模型 + 工具 + 提示词的组合体，职责单一、可独立测试。

## 文件说明

| 文件 | 模型 | 工具 | 提示词 | 职责 | 状态 |
|------|------|------|--------|------|------|
| `web_researcher.py` | Qwen-Max | search_tools | research_prompt | 联网搜索、抓取网页内容 | ✅ |
| `local_wiki.py` | Qwen-Max | LanceDB 向量检索 | - | 本地知识库语义查询 | ✅ |
| `wiki_analyst.py` | Qwen-Max | file_tools | wiki_prompt | **只读不做写**：内存中碰撞新旧知识，输出分析报告 | ✅ |
| `wiki_writer.py` | Qwen-Max | edit_tools | wiki_prompt | **只写不分析**：接收报告，执行原子性磁盘写入 | ✅ |
| `ppt_maker.py` | Qwen-Max | ppt_tools | ppt_prompt | 根据大纲生成 PPT | 🔧 |
| `vision_analyst.py` | Qwen-VL | vision_tools | - | 图片/OCR 分析 | 🔧 |

## 两步思维链（Two-Step CoT）

维基类操作遵循严格的**职责分离**：

```
用户输入 (上传新资料)
    ↓
wiki_analyst   ← 只读内存分析，不碰磁盘
    ↓ (输出 JSON 分析报告)
wiki_writer    ← 接收报告，执行原子性 str_replace
```

**为什么不能合并为一个 Agent？**
- 单一 Agent 在长对话中容易"跳步"：还没分析完就开始写
- 两步分离后，分析师专心找张力（Tension），撰稿人专心精确写入
- 报告是 JSON 可验证，磁盘操作可原子回滚

## 扩展指引

1. 新增 Agent：参考 `wiki_analyst.py` 的结构
2. 注册到 `app.py`：在 AgentOS 中添加新的 `agent_id`
3. 新增路由规则：在 `boss_prompt.py` 中添加 if/else 分支

## 注意事项

- `wiki_analyst` 和 `wiki_writer` 严格串行执行（通过 `workflows/ingest_flow` 串联）
- 禁止任何 Agent 直接调用 `open(...)` 或 `Path.write_text()` 写磁盘，必须通过 `tools/` 封装
