# prompts/ — 提示词工程库

> **将 System Prompt 从 Python 代码中解耦**。独立维护、版本可控，像改文档一样调整 Agent 行为。

## 文件说明

| 文件 | 定义 | 调用方 |
|------|------|--------|
| `boss_prompt.py` | 主管 Agent 的路由规则：判断任务类型，分发给对应子 Agent | `app.py` |
| `research_prompt.py` | 深度研究协议：搜索策略、引用格式、Markdown 输出规范 | `web_researcher.py` |
| `wiki_prompt.py` | Wiki 维护者角色定义：wiki_analyst + wiki_writer 的行为准则 | `wiki_analyst.py` / `wiki_writer.py` |
| `ppt_prompt.py` | PPT Agent 的排版指令：配色方案、字体层级、内容密度控制 | `ppt_maker.py` 🔧 |

## 提示词加载机制

`wiki_prompt.py` 实现了 `load_protocols()` 函数，在构建 System Prompt 时**自动合并** `protocols/` 下的两份协议文件：

```python
from prompts.wiki_prompt import build_analyst_system_prompt
prompt = build_analyst_system_prompt()
# 内部自动读取 purpose.md + schema.md，拼入 prompt
```

## 扩展指引

- 修改 Agent 语气/格式 → 编辑对应 `.py` 中的 prompt 字符串
- 修改知识库操作规范 → 编辑 `protocols/schema.md` 或 `purpose.md`（无需改 Python 代码）
- 新增 Agent 类型 → 在本目录新建 `xxx_prompt.py`，参考 `wiki_prompt.py` 的 `load_protocols()` 模式
