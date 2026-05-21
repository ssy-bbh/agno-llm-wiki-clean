# workflows/ — 确定性工作流层

用 Workflow 替代自由度过高的 Agent 对话。对于需要按固定步骤执行的操作，必须使用 Workflow 确保每一步都被执行且不可跳过。

## 文件说明

| 文件 | 作用 | 调用方式 |
|------|------|---------|
| `ingest_flow.py` | **摄入流水线**：读取来源 → wiki_analyst 分析 → wiki_editor 比对 → wiki_writer 写入 → 追加日志。严格串行，防止自由发挥 | `IngestFlow(source_file="paper.pdf").run()` |
| `lint_flow.py` | **审查流水线**：扫描所有 wiki 页面 → 检测死链和孤立页面 → 自动编织反向链接 | `LintFlow().run()` |
| `query_flow.py` | **查询路由**：Team[local_wiki + web_researcher] → summarizer agent → 最终 Markdown 报告 | `QueryFlow(query="...").run()` |

## ingest_flow.py — 摄入流水线

严格的串行流程，防止以下问题：
- ❌ 分析还没做完就开始写磁盘
- ❌ 还没更新 `index.md` 就去修改概念页
- ❌ 写完后忘记追加审计日志

```
source → wiki_analyst 分析 → wiki_editor 比对 → wiki_writer 写入 → log
```

## lint_flow.py — 审查流水线

| 检查项 | 说明 |
|--------|------|
| 死链 | `[[target]]` 引用但文件不存在 |
| 孤立页面 | 文件存在但从未被任何 `[[]]` 引用 |
| 反向链接 | 自动为被引用页面追加 backlink |

## query_flow.py — 查询路由

```
用户查询 → Team[local_wiki + web_researcher] → summarizer → Markdown 报告
```

结合本地知识库和联网搜索，由 summarizer agent 汇总输出最终报告。

## 扩展指引

- **新增工作流**：在本目录新建 `xxx_flow.py`，编排已有 Agent 和工具
- **定时执行**：在 `app.py` 或 crontab 中调用 `LintFlow().run()` 定期审查
- **原子性保障**：每步操作完成后立即追加 `log.md`，支持事后审计
