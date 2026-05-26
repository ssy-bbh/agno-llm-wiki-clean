"""
workflows/query_flow.py — 终极查询流水线 (支持用户级工作区选择与历史上下文合流)
"""
import sys
import re
import difflib
from pathlib import Path
import json
import asyncio

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from tools.search_tools import search_web_text, search_multimodal_image
from agents.wiki_query import WikiRouter, WikiResponder

class QueryFlow:
    def __init__(self):
        # ✅ 完美保留并初始化你真实的智能体组件
        self.router = WikiRouter()
        self.responder = WikiResponder()
        self.wiki_root = PROJECT_ROOT / "data" / "wiki"

    def _get_workspace_list(self) -> list:
        """提供给前端的 API：获取当前所有合法的工作区名称"""
        if not self.wiki_root.exists():
            return []
        return [d.name for d in self.wiki_root.iterdir() if d.is_dir()]

    def _read_specific_map(self, workspace_name: str) -> str:
        map_path = self.wiki_root / workspace_name / "index.md"
        if map_path.exists():
            return map_path.read_text(encoding="utf-8")
        return "该工作区暂无导航地图。"

    def _read_local_concepts(self, workspace_name: str, concepts: list) -> str:
        """物理动作：在选定的工作区内提取特定概念（双向拆解 + 别名雷达网 + difflib 容错）"""
        context = ""
        concepts_dir = self.wiki_root / workspace_name / "concepts"

        if not concepts_dir.exists():
            return context

        all_md_files = list(concepts_dir.glob("*.md"))

        # ==========================================
        # 💡 核心算法保留：建立【多重别名雷达图】
        # ==========================================
        alias_map = {}
        for f in all_md_files:
            stem = f.stem.lower()
            alias_map[stem] = f  # 1. 注册完整原名

            # 2. 对物理文件名也进行中英文括号拆解，注册分身代号
            file_parts = [p.strip() for p in re.split(r'[(（)）]', stem) if p.strip()]
            for p in file_parts:
                if p not in alias_map:  # 优先保留最原始的映射，防冲突
                    alias_map[p] = f

        available_aliases = list(alias_map.keys())

        for concept in concepts:
            # 基础脱壳
            clean_concept = concept.replace("[", "").replace("]", "").strip()
            safe_name = clean_concept.replace("/", "_").replace("\\", "_")
            lower_name = safe_name.lower()

            # 🛡️ 防线 1：直接命中全名 或 物理文件的拆解代号
            if lower_name in alias_map:
                match_file = alias_map[lower_name]
                context += f"【🚨本地知识 == {match_file.name} ==】\n{match_file.read_text(encoding='utf-8')}\n\n"
                print(f"  -> 📂 [装载弹药] 成功提取物理笔记: {match_file.name}")
                continue

            print(f"  ⚠️ [调度室] 精确/别名匹配失效 [{safe_name}]，启动算法降级嗅探...")

            # 🛡️ 防线 2：反向拆解（LLM吐出长词，物理文件是短词）
            parts = [p.strip() for p in re.split(r'[(（)）]', lower_name) if p.strip()]
            found_by_parts = False
            for part in parts:
                if part in alias_map:
                    part_file = alias_map[part]
                    context += f"【🚨本地拆解挂载 == {part_file.name} ==】\n{part_file.read_text(encoding='utf-8')}\n\n"
                    print(f"  -> 🔍 [反向拆解] 成功通过别名 [{part}] 命中物理笔记: {part_file.name}")
                    found_by_parts = True
                    break

            if found_by_parts:
                continue

            # 🛡️ 防线 3：高相似度容错 (依然保持 0.85 的严格阈值)
            close_matches = difflib.get_close_matches(lower_name, available_aliases, n=1, cutoff=0.85)
            if close_matches:
                match_stem = close_matches[0]
                match_file = alias_map[match_stem]
                context += f"【🚨本地相似挂载 == {match_file.name} ==】\n{match_file.read_text(encoding='utf-8')}\n\n"
                print(f"  -> 🧲 [相似纠错] 成功通过高相似度 ({lower_name} -> {match_stem}) 命中笔记: {match_file.name}")
            else:
                print(f"  ❌ [调度室] 彻底未找到相关笔记: [{safe_name}]")

        return context

    def _fuzzy_find_local_files(self, workspace_name: str, fuzzy_keywords: list) -> str:
        """物理动作：根据 AI 的猜测，在工作区内进行地毯式模糊搜索"""
        if not fuzzy_keywords:
            return ""

        workspace_dir = self.wiki_root / workspace_name
        if not workspace_dir.exists():
            return ""

        context = ""
        found_files = set()

        all_md_files = list(workspace_dir.rglob("*.md"))

        for keyword in fuzzy_keywords:
            if not keyword.strip():
                continue

            keyword_lower = keyword.lower()
            for file_path in all_md_files:
                if keyword_lower in file_path.stem.lower() and file_path not in found_files:
                    found_files.add(file_path)
                    try:
                        context += f"【🚨本地模糊匹配命中 == {file_path.name} ==】\n{file_path.read_text(encoding='utf-8')}\n\n"
                        print(f"  -> 🔍 [雷达嗅探] 模糊匹配成功：关键词 [{keyword}] 命中了物理笔记 [{file_path.name}]")
                    except Exception as e:
                        pass

        return context

    def execute(self, user_question: str, target_workspace: str = ""):
        """
        🚀 极客控制台 (CLI) 核心调度入口（完美修复了之前断裂的结构）
        """
        print(f"\n👤 【用户提问】: {user_question}")

        if target_workspace:
            print(f"📁 【锁定工作区】: 用户已明确指定为 -> [{target_workspace}]")
        else:
            print("⚠️ 【警告】: 用户未指定工作区，系统将无法挂载任何本地地图！")

        local_concepts = []
        fuzzy_keywords = []
        needs_web = True
        search_query = user_question

        if target_workspace:
            print("-" * 60)
            print("🗺️ [调度室] 正在呼叫寻路者读取指定工作区的局部地图...")
            index_map = self._read_specific_map(target_workspace)
            try:
                decision = self.router.route(user_question, index_map)
                print(f"  -> 🎯 寻路裁决: {decision}")
                local_concepts = decision.get("local_concepts", [])
                fuzzy_keywords = decision.get("fuzzy_keywords", [])
                needs_web = decision.get("needs_web_search", True)
                search_query = decision.get("search_query", user_question)
            except Exception as e:
                print(f"❌ 路由模块崩溃: {e}")

        print("\n" + "-" * 60)
        print("🚚 [调度室] 正在按裁决清单装载弹药...")

        local_context = ""
        if target_workspace:
            if local_concepts:
                local_context += self._read_local_concepts(target_workspace, local_concepts)
            if fuzzy_keywords:
                local_context += self._fuzzy_find_local_files(target_workspace, fuzzy_keywords)

        web_context, image_context = "", ""
        if needs_web and search_query:
            print(f"  -> 🌐 [调度室] 授权触发外脑，检索词: [{search_query}]")
            web_context = search_web_text(search_query)
            images = search_multimodal_image(search_query)
            if images:
                image_context = f"![{images[0].title}]({images[0].image_url})"
                print("  -> 👁️ 成功挂载视觉辅助图床。")

        print("\n" + "-" * 60)
        print("🗣️ [调度室] 弹药装填完毕，Responder 开始解答：\n")
        try:
            response_stream = self.responder.answer(user_question, local_context, web_context, image_context)
            for chunk in response_stream:
                text = chunk.content if hasattr(chunk, 'content') else str(chunk)
                if text and text != "None":
                    print(text, end="", flush=True)
            print("\n")
        except Exception as e:
            print(f"\n❌ 答疑模块崩溃: {e}")

    # ==========================================
    # 🔗 核心新增：Web端专用的流式生成器 (完美嵌合上下文记忆)
    # ==========================================
    async def stream_execute(self, user_question: str, target_workspace: str, history: list = None):
        """Web 端专用的流式生成器 (返回 SSE NDJSON)"""
        if history is None:
            history = []

        def format_log(msg: str):
            print(msg)
            return f"data: {json.dumps({'type': 'log', 'content': msg})}\n\n"

        yield format_log(f"👤 收到提问: {user_question}")
        await asyncio.sleep(0.01)

        yield format_log(f"📁 锁定工作区: [{target_workspace if target_workspace else '全局漫游'}]")
        await asyncio.sleep(0.01)

        local_concepts = []
        fuzzy_keywords = []
        needs_web = True
        search_query = user_question
        decision = {}

        # L2 路由
        if target_workspace:
            yield format_log("🗺️ [调度室] 正在呼叫寻路者读取局部地图...")
            await asyncio.sleep(0.01)
            index_map = self._read_specific_map(target_workspace)
            try:
                decision = self.router.route(user_question, index_map)
                yield format_log("  -> 🎯 寻路裁决完毕。")
                await asyncio.sleep(0.01)
            except Exception as e:
                yield format_log(f"❌ 路由裁决异常，已自动降级: {e}")
                await asyncio.sleep(0.01)

            local_concepts = decision.get("local_concepts", [])
            fuzzy_keywords = decision.get("fuzzy_keywords", [])
            needs_web = decision.get("needs_web_search", True)
            search_query = decision.get("search_query", user_question)

        # 装载弹药
        yield format_log("🚚 [调度室] 正在按裁决清单装载本地弹药...")
        await asyncio.sleep(0.01)
        local_context = ""
        if target_workspace:
            if local_concepts:
                local_context += self._read_local_concepts(target_workspace, local_concepts)
                yield format_log(f"  -> 📂 成功精确装载 {len(local_concepts)} 个概念。")
                await asyncio.sleep(0.01)
            if fuzzy_keywords:
                local_context += self._fuzzy_find_local_files(target_workspace, fuzzy_keywords)
                yield format_log("  -> 🔍 模糊嗅探装载完毕。")
                await asyncio.sleep(0.01)

        web_context, image_context = "", ""
        if needs_web and search_query:
            yield format_log(f"  -> 🌐 [调度室] 触发全网雷达检索: [{search_query}]")
            await asyncio.sleep(0.01)
            web_context = search_web_text(search_query)
            images = search_multimodal_image(search_query)
            if images:
                image_context = f"![{images[0].title}]({images[0].image_url})"

        # 💡 记忆流闭合点：在此处将前端传来的历史回忆，与本地抽取的弹药无缝合流
        if history:
            history_str = "【前情对话回忆录】\n"
            for msg in history[-5:]:  # 提取最近 5 轮，防止 token 溢出
                role_label = "用户" if msg.get('role') == 'user' else 'AI'
                history_str += f"{role_label}: {msg.get('content')}\n"
            history_str += "\n"
            # 前置拼装，让大模型在看文件前先看一眼刚才聊过什么
            local_context = history_str + local_context

        yield format_log("🗣️ 历史记忆与本地沙箱弹药装填完毕，开始驱动外脑生成回答：")
        await asyncio.sleep(0.01)

        # 核心：流式输出你真实的 WikiResponder 大模型回答
        # 核心：流式输出你真实的 WikiResponder 大模型回答
        try:
            response_stream = self.responder.answer(user_question, local_context, web_context, image_context)
            for chunk in response_stream:
                text = chunk.content if hasattr(chunk, 'content') else str(chunk)
                if text and text != "None":
                    yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"
                    await asyncio.sleep(0.01)

            # ==========================================
            # 💡 完美适配 Python 3.11 的强行追加逻辑
            # ==========================================
            if image_context:
                yield format_log("👁️ [调度室] 正在向前端渲染管道强行注入视觉参考图床...")
                await asyncio.sleep(0.01)

                # ✅ 1. 先在外部拼装好带换行的 Markdown 文本（大括号内绝无反斜杠）
                image_markdown = f"\n\n### 🌐 检索参考图片:\n{image_context}\n"

                # ✅ 2. 构建干净的字典对象
                payload = {"type": "text", "content": image_markdown}

                # ✅ 3. 序列化输出（大括号内部只有 json.dumps，反斜杠在外面，3.11 完美通行）
                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(0.01)

        except Exception as e:
            yield format_log(f"❌ 答疑模块崩溃: {e}")
            await asyncio.sleep(0.01)

        yield f"data: {json.dumps({'type': 'done'})}\n\n"


# ==========================================
# 🚀 极客控制台 (CLI 交互入口)
# ==========================================
if __name__ == "__main__":
    flow = QueryFlow()
    available_workspaces = flow._get_workspace_list()

    print("\n" + "=" * 60)
    print("🚀 [LLM-Wiki 终端控制台] 引擎点火完毕！")
    print("=" * 60)

    if not available_workspaces:
        print("\n⚠️ 警告：在 data/wiki 下未检测到任何工作区文件夹！将强制进入全局漫游模式。")
        target_ws = ""
    else:
        print("\n📂 请选择你要挂载的本地工作区：")
        print("  [0] 🌍 全局漫游 (不挂载本地知识，纯粹依靠大模型和外脑)")
        for idx, ws in enumerate(available_workspaces, 1):
            print(f"  [{idx}] 📁 {ws}")

        choice = input("\n👉 请输入编号 (按回车默认 0): ").strip()

        target_ws = ""
        if choice.isdigit() and 0 < int(choice) <= len(available_workspaces):
            target_ws = available_workspaces[int(choice) - 1]

    print("\n" + "=" * 60)
    print(f"✅ 系统锁定完毕！当前运行状态：[{target_ws if target_ws else '🌍 全局漫游'}]")
    print("💡 提示: 输入 'exit' 或 'quit' 可随时退出控制台")
    print("=" * 60)

    while True:
        try:
            user_question = input("\n👤 你的问题: ").strip()

            if user_question.lower() in ['exit', 'quit']:
                print("\n👋 引擎关闭，再见！")
                break
            if not user_question:
                continue

            flow.execute(user_question, target_workspace=target_ws)

        except KeyboardInterrupt:
            print("\n\n👋 检测到强制中断，引擎关闭。")
            break