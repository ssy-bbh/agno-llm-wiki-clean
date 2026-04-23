# workflows/ — 确定性工作流层

> **用 Workflow 替代自由度过高的 Agent 对话**。对于需要按固定步骤执行的操作（如摄入→比对→写入→日志），必须使用 Workflow 确保每一步都被执行且不可跳过。

## 目录说明

| 文件 | 作用 | 调用方式 |
|------|------|---------|
| `ingest_flow.py` | **摄入流水线**：读取来源 → 分析碰撞 → 原子写入 → 追加日志，严格串行 | `IngestFlow(source_file="paper.pdf").run()` |
| `lint_flow.py` | **审查流水线**：扫描所有 wiki 页面 → 检测死链/孤立页面 → 追加审计日志 | `LintFlow().run()` |

## ingest_flow.py — 摄入流水线

### 为什么必须用 Workflow？

当摄入新知识时，只让 Agent 自由发挥会出现以下问题：
- ❌ 分析还没做完就开始写磁盘
- ❌ 还没更新 `index.md` 就去修改具体概念页
- ❌ 写完后忘记追加审计日志
- ❌ 并发写入同一页面导致冲突

`ingest_flow.py` 通过 Agno `Workflow` 强制串行：

```
Step 1: wiki_analyst.ingest()   ← 只读不做写，输出 JSON 分析报告
    ↓
Step 2: wiki_writer.apply()    ← 接收报告，执行原子性磁盘操作
```

### 使用示例

```python
from workflows import IngestFlow

flow = IngestFlow(
    source_file="attention-is-all-you-need.pdf",
    context="这是 Transformer 论文"
)
result = flow.run()
print(result["new_concepts"])   # ['self-attention', 'multi-head-attention', ...]
```

## lint_flow.py — 审查流水线

### 检查内容

| 检查项 | 说明 |
|--------|------|
| 死链 | `[[target]]` 引用但文件不存在 |
| 孤立页面 | 文件存在但从未被任何 `[[]]` 引用 |
| index.md 超载 | 超过 500 行时自动拆分 |

### 使用示例

```python
from workflows import LintFlow

result = LintFlow().run(verbose=True)
print(result["dead_links"])
print(result["orphans"])
```

## 扩展指引

- 新增工作流：在本目录新建 `xxx_flow.py`，继承 `Workflow` 类
- 定时执行：在 `app.py` 或 crontab 中调用 `LintFlow().run()` 定期审查
- 原子性保障：每步操作完成后立即追加 `log.md`，支持事后审计
