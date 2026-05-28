# prompts/ — 提示词工程库（已废弃）

> ⚠️ **注意**：本目录下的 `.py` 文件均为历史遗留，内容已清空（0 字节）。
> 所有 Agent 的 System Prompt 现已**内联到各 Agent 的 `instructions` 字符串**中。

## 当前提示词位置

| Agent | 提示词位置 |
|-------|-----------|
| `wiki_analyst` | `agents/wiki_analyst.py` → `instructions` |
| `wiki_editor` | `agents/wiki_editor.py` → `instructions` |
| `wiki_writer` | `agents/wiki_writer.py` → `instructions` |
| `web_researcher` | `agents/web_researcher.py` → `instructions` |
| `local_wiki` | `agents/local_wiki.py` → `instructions` |
| `wiki_query` | `agents/wiki_query.py` → `instructions` |
| IntentRouter | `app.py` → IntentRouter Agent `instructions` |

## 知识库协议层（仍在使用）

`protocols/` 目录下的 Markdown 协议文件仍然有效，Agent 运行时按需读取：

- `protocols/purpose.md` — 知识库使命边界、核心论点
- `protocols/schema.md` — 操作 SOP：双链语法、页面模板

## 扩展指引

- **修改 Agent 行为**：直接编辑对应 Agent `.py` 文件中的 `instructions` 字符串
- **修改知识库规范**：编辑 `protocols/schema.md` 或 `protocols/purpose.md`
- **新增 Agent**：在新 `.py` 文件中内联 `instructions`，无需在此目录新建文件
