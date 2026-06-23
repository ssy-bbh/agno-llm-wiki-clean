# core/ — 核心基座层

全局基础设施，所有其他模块共享的底层能力。

## 文件说明

| 文件 | 职责 |
|------|------|
| `config.py` | Pydantic `Settings`，读取 `.env` 文件，提供全局单例。集中管理 LLM 模型 ID、API Key、向量库配置等。 |
| `llm_factory.py` | 模型工厂：通过 `OpenAILike` + DashScope 兼容 API 创建 Qwen-Max（文本）和 Qwen-VL-Max（多模态）实例。内置 `role_map` 锁定 System Prompt 权限，防提示词篡改。 |
| `memory_manager.py` | 封装 Agno SQLite Memory（会话历史）和 LanceDB（向量检索）的连接与初始化。 |

## 设计原则

1. **配置集中化**：API Key、模型选择、超参数全在 `config.py`
2. **LLM 统一创建**：所有 Agent 通过 `get_qwen_model()` 从工厂获取模型实例
3. **存储路径统一**：SQLite/LanceDB 路径由 `memory_manager` 集中管理

## 扩展指引

- **切换模型**：修改 `llm_factory.py` 中的模型 ID
- **新增全局配置**：在 `config.py` 的 `Settings` 类中新增字段
- **切换向量库**：修改 `memory_manager.py` 中的 Embedding 模型
