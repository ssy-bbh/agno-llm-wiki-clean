# data/ — 数据输入输出区

> **读写分离的物理拓扑**。舍弃了笼统的"输入/输出"概念，严格执行读写分离。

## 目录结构

```
data/
├── raw/              # 【只读】原始来源层
│   └── *.pdf / *.docx / *.md / *.png ...
│
└── wiki/             # 【可写】维基编译层，由大模型全权维护
    ├── concepts/      # 知识概念节点页面
    ├── entities/      # 具体人物、项目、产品等实体页面
    ├── index.md      # 全局导航地图（每次查询或写入前必读）
    └── log.md        # Append-only 审计日志（只能追加，不能编辑）
```

## 读写权限矩阵

| 目录 | Agent 读 | Agent 写 | 人类编辑 |
|------|---------|---------|---------|
| `data/raw/` | ✅ 可以 | ❌ 禁止 | ✅ 可以（上传新文件） |
| `data/wiki/concepts/` | ✅ 可以 | ✅ via edit_tools | ✅ 可以 |
| `data/wiki/entities/` | ✅ 可以 | ✅ via edit_tools | ✅ 可以 |
| `data/wiki/index.md` | ✅ 可以 | ✅ via edit_tools | ✅ 可以 |
| `data/wiki/log.md` | ✅ 可以 | ✅ via append_to_log() | ❌ 禁止 |

## index.md 的角色

`index.md` 是整个知识库的**全局寻址核心**，包含：
- 顶层分类结构（Concepts / Entities）
- 最近更新清单
- 孤立页面警告
- 跨领域关联索引

每次 `ingest_flow` 完成后必须同步更新；`lint_flow` 会定期检查其一致性。

## log.md 的角色

Append-only 审计日志，记录格式：

```markdown
- **2026-04-22 16:00** | CREATE | attention-mechanism.md | 新建 concept 页面
- **2026-04-22 16:01** | EDIT | transformer-architecture.md | 追加 [[attention-mechanism]]
- **2026-04-22 16:05** | LINT | | ✅ 未发现问题
```

## 安全边界

- `file_tools.py` 强制校验路径，禁止 `../` 跳出 `data/wiki/`
- `edit_tools.py` 所有写操作必须通过 `str_replace()` 或 `append_to_log()`
- 原始数据在 `raw/` 中永不修改，支持重新编译（Re-compile）
