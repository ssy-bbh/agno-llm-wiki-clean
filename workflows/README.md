# workflows/ — 确定性工作流层

用 Workflow 替代自由度过高的 Agent 对话。对于需要按固定步骤执行的操作，必须使用 Workflow 确保每一步都被执行且不可跳过。

## 文件说明

| 文件 | 作用 | 调用方式 |
|------|------|---------|
| `ingest_flow.py` | **摄入流水线**：Map-Reduce 三阶段并发（12线程提取 → 概念聚类 → 逐概念融合） | `IngestFlow().run("path/to/file.pdf")` |
| `lint_flow.py` | **审查流水线**：扫描所有 wiki 页面 → 检测死链和孤立页面 → 自动编织反向链接 | `LintFlow().run()` |
| `query_flow.py` | **查询路由**：Team[local_wiki + web_researcher] → summarizer agent → 最终 Markdown 报告 | `get_query_workflow()` 返回 Workflow 对象 |
| `autofill_flow.py` | **幽灵节点填补**：扫描双链统计入度 → 探测真空节点（有引用无页面）→ 自动合成填充 | `AutoFillFlow(threshold=5).run()` |

## ingest_flow.py — Map-Reduce 知识摄取流水线

三阶段并发架构，兼顾效率与质量：

```
原始文档
  │
  ├── [Phase 1: MAP]    12线程并发调用 WikiAnalyst 提取各知识块的概念+摘要
  ├── [Phase 2: SHUFFLE] 按概念聚类（同义词解构引擎：英文名(中文)格式）
  └── [Phase 3: REDUCE] 逐个概念启动 WikiEditor 融合 → WikiWriter 写盘
```

- **Phase 1 MAP**：无锁并发，12 线程同时提取，大幅加速
- **Phase 2 SHUFFLE**：基于双语解构（`Self-Attention (自注意力机制)` 等格式）合并同名碎片
- **Phase 3 REDUCE**：逐概念重启新鲜 `WikiEditor`，消除记忆污染；Token 超限自动截断保护

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

- 基于 Agno `Team` 编排，队长路由请求到 Local Wiki 或 Web Researcher
- 最终由 Summarizer Agent 汇总输出结构化 Markdown 报告

## autofill_flow.py — 幽灵节点自动填补

````
全盘扫描 → 统计 [[双链]] 入度 → 过滤真空节点 → 溯源上下文 → 主编合成 → 写盘
```

- 扫描 concepts 目录下所有 Markdown 文件，提取 `[[xxx]]` 双向链接
- 统计每个概念的入度，被引用 ≥ threshold 次但无实体页面的即为「真空节点」
- 自动修复异名假空节点（链接重定向），再对纯正真空节点逐个合成

## 扩展指引

- **新增工作流**：在本目录新建 `xxx_flow.py`，编排已有 Agent 和工具
- **定时执行**：在 `app.py` 或 crontab 中调用 `LintFlow().run()` 定期审查
- **原子性保障**：每步操作完成后立即追加 `log.md`，支持事后审计
