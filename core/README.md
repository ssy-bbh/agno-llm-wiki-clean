# core/ — 核心基座层

> 本层是整个项目的"地基石"，所有其他模块共享这些基础设施。

## 模块说明

| 文件 | 职责 |
|------|------|
| `config.py` | 用 `python-dotenv` 读取 `.env`，暴露 `settings` 全局单例供各模块引用 |
| `llm_factory.py` | 统一定义 `Qwen-Max`（文本模型）和 `Qwen-VL`（多模态模型）的实例化逻辑 |
| `memory_manager.py` | 封装 Agno 的 SQLite Memory（会话历史）和 LanceDB（向量检索）的连接与初始化 |

## 设计原则

1. **只在这里改配置**：API Key、模型选择、超参数等全局变量全部集中在 `config.py`
2. **不重复初始化**：LLM 实例由 `llm_factory` 统一定义，各 Agent 按需引用而非各自 `OpenAI(...)`
3. **存储路径统一**：SQLite DB 路径、LanceDB 索引路径统一在 `memory_manager` 中管理

## 扩展指引

- 切换模型：`llm_factory.py` 中替换 `model_id`
- 切换向量库：`memory_manager.py` 中替换 Embedding 模型（如 `nomic-embed-text`）
- 新增全局配置：在 `config.py` 的 `Settings` 类中新增字段
