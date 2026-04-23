# tools/ — 技能工具箱

> **拓展新能力的核心入口**。每个工具文件封装一类外部能力，Agent 按需组合调用。

## 文件说明

| 文件 | 能力 | 状态 |
|------|------|------|
| `search_tools.py` | DuckDuckGo 联网搜索 + Newspaper4k 全文抓取 | ✅ 已实现 |
| `file_tools.py` | 读写隔离：所有操作强制圈禁在 `data/wiki/` 内，路径越界直接抛异常 | ✅ 已实现 |
| `edit_tools.py` | `str_replace` 精密替换 + `append_to_log()` 审计 + `create_page()` 新建页面 | ✅ 已实现 |
| `ppt_tools.py` | python-pptx 封装，"根据大纲生成一页 PPT"函数 | 🔧 扩展中 |
| `vision_tools.py` | 图片读取、OCR、截图等视觉预处理工具 | 🔧 扩展中 |

## 核心安全机制

### file_tools.py
```
WIKI_ROOT = data/wiki/  # 硬编码，Agent 无法跳出
_check_path() 在每次操作前校验，拒绝 ../ 目录遍历攻击
```
**禁止**：`file_tools.write_file()` 已被重写，直接抛 `PermissionError`。
**允许**：`append_to_file()` 仅限 `data/wiki/log.md`。

### edit_tools.py
- `str_replace(old, new)`：必须精确匹配原文，防止 LLM 全量覆写导致 Markdown 格式错乱
- `append_to_log()`：Append-only，只能追加审计日志，不能写其他内容
- `create_page()`：自动在 `log.md` 追加创建记录

## 新增工具流程

1. 新建 `xxx_tools.py`
2. 参考 `file_tools.py` 的 `_check_path()` 做安全隔离
3. 在对应 Agent 的 `tools=` 参数中注册

## 与 protocols/ 的关系

工具只负责"怎么做"，不负责"做什么"。做什么由 `prompts/` 和 `protocols/` 定义。
