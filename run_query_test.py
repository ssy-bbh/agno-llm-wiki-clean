"""
run_query_test.py — Query Flow 终极双智能体 & 外脑触角集成测试
"""
import os
import sys

# ⚠️ 确保你已经设置了百炼 API Key，如果没有，请在这里取消注释并填入
# os.environ["ALIYUN_API_KEY"] = "sk-xxxxxxxxxxxxxxxxxx"

# 尝试导入我们刚刚写的模块 (如果路径找不到，请确保你在项目根目录运行)
try:
    from tools.search_tools import search_web_text, search_multimodal_image
    from agents.wiki_query import WikiRouter, WikiResponder
except ImportError as e:
    print(f"❌ 导入失败，请检查模块路径是否正确: {e}")
    sys.exit(1)


def run_test():
    print("\n" + "=" * 60)
    print("🧪 [实验室] 启动 Query Flow 全链路测试")
    print("=" * 60)

    # 1. 模拟一个非常贫乏的本地地图
    mock_index_map = """
    # 导航地图
    ## 计算机视觉
    - [[YOLOv4]]
    - [[ResNet]]
    """

    # 2. 故意问一个本地绝对没有，且非常前沿的问题！
    # 这会逼迫 WikiRouter 触发 needs_web_search = True
    user_question = "详细解释一下最新的 YOLOv10 模型，它相比之前的版本去掉了什么核心结构？"
    print(f"👤 【用户提问】: {user_question}\n")

    # ==========================================
    # 🗺️ 阶段 1: 寻路者决策
    # ==========================================
    print("-" * 60)
    print("🗺️ [WikiRouter] 正在对照本地地图进行路由决策...")
    router = WikiRouter()

    try:
        decision = router.route(user_question, mock_index_map)
        print(f"  -> 🎯 决策结果: {decision}")
    except Exception as e:
        print(f"  -> ❌ Router 执行失败: {e}")
        return

    # ==========================================
    # 🕸️ 阶段 2: 赛博触角抓取 (如果被触发)
    # ==========================================
    print("\n" + "-" * 60)
    local_context = "本地知识库中未找到该概念，这是个幽灵节点或全新知识。"
    web_context = ""
    image_context = ""

    if decision.get("needs_web_search"):
        search_query = decision.get("search_query", "YOLOv10")
        print(f"🌐 [系统调度] 寻路者申请调用外脑！正在全网搜索: {search_query} ...")

        # 测试搜文
        web_context = search_web_text(search_query)
        print(f"  -> 📄 搜文完毕，已获取 {len(web_context)} 字符的情报。")

        # 测试搜图
        images = search_multimodal_image(search_query)
        if images:
            image_context = f"![{images[0].title}]({images[0].image_url})"
            print(f"  -> 👁️ 搜图完毕，已捕获视觉素材: {images[0].title}")
    else:
        print("🛡️ [系统调度] 寻路者认为纯本地知识即可解答，未触发外脑。")

    # ==========================================
    # 🗣️ 阶段 3: 答疑者流式输出
    # ==========================================
    print("\n" + "-" * 60)
    print("🗣️ [WikiResponder] 答疑者正在整合图文情报，开始解答：\n")

    responder = WikiResponder()

    try:
        # 这里的迭代方式取决于你用的 Agno Agent stream=True 时的具体返回值
        # 通常是 generator，每次 yield 一个 chunk
        response_stream = responder.answer(
            user_query=user_question,
            local_context=local_context,
            web_context=web_context,
            image_context=image_context
        )

        for chunk in response_stream:
            # Agno 的流式输出通常是一个 RunResponse 对象，或者直接 yield 文本
            text_chunk = chunk.content if hasattr(chunk, 'content') else str(chunk)
            print(text_chunk, end="", flush=True)

    except Exception as e:
        print(f"\n❌ Responder 执行失败: {e}")

    print("\n\n" + "=" * 60)
    print("✅ 测试闭环完成！")


if __name__ == "__main__":
    run_test()