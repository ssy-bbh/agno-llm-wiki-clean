"""
core/llm_factory.py — 统一模型工厂（BYOK 感知）

通过 threading.local() 自动感知当前请求的用户上下文，
委托给 model_router 返回用户配置的模型实例。
Agent 文件无需修改，仍然调用 get_qwen_model() 即可。
"""
import os
import threading
from dotenv import load_dotenv
from agno.models.openai.like import OpenAILike

load_dotenv()

# ── 线程级用户上下文 ──
_ctx = threading.local()


def set_user_context(user_id: str = "", role: str = "user"):
    """在请求入口设置当前线程的用户 ID 和角色"""
    _ctx.user_id = user_id
    _ctx.role = role


def get_user_context() -> str:
    """获取当前线程的用户 ID"""
    return getattr(_ctx, "user_id", "")


def get_user_role() -> str:
    """获取当前线程的用户角色"""
    return getattr(_ctx, "role", "user")


def get_qwen_model(model_id=None):
    """
    获取 LLM 模型实例（兼容旧接口名）。

    优先级：
    1. 用户自己配置的 API Key（BYOK）
    2. 管理员 → 回退系统默认 QWEN_API_KEY
    3. 普通用户没配 Key → 抛错提示去设置页配置
    """
    user_id = get_user_context()
    role = get_user_role()

    if user_id:
        try:
            from core.model_router import get_model_for_user
            model = get_model_for_user(user_id=user_id)
            if model_id:
                model.id = model_id
            return model
        except Exception:
            # 用户没配任何 API Key
            if role == "admin":
                pass  # 管理员回退到系统默认
            else:
                raise ValueError(
                    "你还没有配置 API Key，无法使用 AI 功能。\n\n"
                    "👉 请点击右上角 ⚙️ **设置** → 选择模型厂商 → 输入你的 API Key 即可开始使用。"
                )

    # 系统默认（管理员回退 / 无用户上下文的后台任务）
    api_key = os.getenv("QWEN_API_KEY")
    if not api_key:
        raise ValueError("⚠️ 系统未配置 QWEN_API_KEY，请在 .env 中设置！")

    return OpenAILike(
        id=model_id or os.getenv("QWEN_MODEL_ID", "deepseek-v4-pro"),
        api_key=api_key,
        base_url=os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        role_map={"system": "system", "user": "user", "assistant": "assistant", "tool": "tool"},
    )
