# tools/ — 技能工具箱

封装外部能力供 Agent 调用，每个工具文件专注一类操作。

## 文件说明

| 文件 | 能力 | 状态 |
|------|------|------|
| `search_tools.py` | DuckDuckGoTools 联网搜索 + Newspaper4kTools 全文抓取 | ✅ |
| `file_tools.py` | 安全文件操作：路径锁定在 `data/wiki/`，拒绝 `../` 越界遍历 | ✅ |
| `edit_tools.py` | `str_replace` 精密局部替换 + `create_page` 新建页面 + `append_to_log` 审计日志。**所有写入必须经过此模块** | ✅ |
| `ppt_tools.py` | python-pptx 封装，根据大纲生成 PPT | 🔧 WIP |
| `vision_tools.py` | 图片读取、OCR 等视觉预处理 | 🔧 WIP |
| `document_parser.py` | 文档解析（PDF 读取、文本分块） | ✅ |

## 安全隔离

- `file_tools.py` 和 `edit_tools.py` 强制校验路径，所有文件操作被圈禁在 `data/wiki/` 内
- Agent 无法越界写入其他目录
- 所有写入操作（新建、编辑、追加日志）统一通过 `edit_tools.py`，确保审计可追溯
