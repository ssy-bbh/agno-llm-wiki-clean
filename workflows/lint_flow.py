import os
import re
import sys
import json
import asyncio
from pathlib import Path

from core.path_resolver import get_wiki_root, USE_MINIO


class LintFlow:
    """
    知识库审查与织网流水线
    负责单沙箱扫描，自动建立反向链接（Backlinks），并清理死链。
    """

    def __init__(self):
        self.link_pattern = re.compile(r'\[\[(.*?)\]\]')

    async def stream_run(self, kb_name: str, user_id: str = ""):
        """
        🚀 Web端专用的流式审查与织网方法 (返回符合 SSE 标准的日志流)
        """

        def format_log(msg: str):
            return f"data: {json.dumps({'type': 'log', 'content': msg})}\n\n"

        yield format_log(f"🕷️ [LintFlow] 启动审查与织网流水线 | 🎯 锁定沙箱: [{kb_name}]")
        await asyncio.sleep(0.01)

        if USE_MINIO:
            # ═══════════════════════════════════════════
            # MinIO 模式
            # ═══════════════════════════════════════════
            from core.storage import get_storage
            from core.path_resolver import minio_concepts_prefix

            s = get_storage()
            prefix = minio_concepts_prefix(user_id, kb_name)
            all_keys = s.list_keys(prefix)
            # 过滤出 .md 文件，排除 index.md 和 mocs/
            concept_keys = [k for k in all_keys if k.endswith(".md") 
                           and not k.endswith("/index.md") 
                           and "/mocs/" not in k]

            if not concept_keys:
                yield format_log(f"⚠️ 该沙箱概念仓为空，无需织网。")
                return

            yield format_log(f"📂 在 [{kb_name}] 核心概念仓中发现 {len(concept_keys)} 个页面。")
            await asyncio.sleep(0.01)

            # 记录映射表： target_concept -> set(source_file_names)
            backlinks_map = {}

            yield format_log("🔍 正在地毯式提取跨文件正向引用引用链...")
            await asyncio.sleep(0.01)

            # 构建文件名索引（用于后续查找）
            filename_index = {}  # clean_name -> key
            for key in concept_keys:
                name = key.split("/")[-1].replace(".md", "")
                clean = name.lower().replace("-", "").replace("_", "").replace(" ", "")
                filename_index[clean] = key

            for key in concept_keys:
                name = key.split("/")[-1].replace(".md", "")
                if name in ["index", "log"]:
                    continue

                try:
                    content = s.read_text(key)
                except Exception as e:
                    yield format_log(f"⚠️ 读取失败: {key} - {e}")
                    continue

                # 找到当前文件里所有的 [[概念]] 和 [[别名|显示文本]]
                links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)

                for target in links:
                    target_clean = target.strip()
                    if not target_clean:
                        continue
                    if target_clean not in backlinks_map:
                        backlinks_map[target_clean] = set()
                    backlinks_map[target_clean].add(name)

            yield format_log(f"🕸️ 扫描完毕，累计发现 {len(backlinks_map)} 个处于引用状态的概念节点。")
            await asyncio.sleep(0.01)

            yield format_log("✍️ 正在自动进行反向链接 (Backlinks) 索引的物理写回...")
            await asyncio.sleep(0.01)

            updated_count = 0
            dead_links = []

            for target_concept, sources in backlinks_map.items():
                # O(1) 索引查找
                clean_target = target_concept.lower().replace("-", "").replace("_", "").replace(" ", "")
                target_key = filename_index.get(clean_target)

                if not target_key:
                    dead_links.append(target_concept)
                    continue

                try:
                    content = s.read_text(target_key)
                except Exception:
                    dead_links.append(target_concept)
                    continue

                # 构造要注入的反向链接字符串
                backlink_section = "\n## Backlinks\n"
                for src in sources:
                    backlink_section += f"- [[{src}]]\n"

                # 简单剥离旧的 Backlinks 及之后的内容
                if "## Backlinks" in content:
                    content = content.split("## Backlinks")[0].strip()

                # 追加新的反向链接
                new_content = content + "\n\n" + backlink_section

                try:
                    s.write_text(target_key, new_content)
                    updated_count += 1
                    target_name = target_key.split("/")[-1]
                    yield format_log(f"  -> 🔗 成功重织反向链接节点: [{target_name}]")
                    await asyncio.sleep(0.01)
                except Exception as e:
                    yield format_log(f"  -> ❌ 写回失败: {target_key} - {e}")

            yield format_log(f"✅ 成功物理更新了 {updated_count} 个实体的拓扑索引！")
            await asyncio.sleep(0.01)

            if dead_links:
                dead_str = ", ".join(list(dead_links)[:5]) + (" ..." if len(dead_links) > 5 else "")
                yield format_log(f"⚠️ 核心警告：全库发现 {len(dead_links)} 个【幽灵死链】(有提及但在库中无文件): {dead_str}")
                await asyncio.sleep(0.01)

            # ═══ OKF: Staleness 检测 + 矛盾积压告警 ═══
            async for msg in self._okf_health_check_minio(s, concept_keys, format_log):
                yield msg

            yield format_log(f"🕸️ [LintFlow] [{kb_name}] 织网完成，沙箱局部知识拓扑已彻底闭环！")
            return

        # ═══════════════════════════════════════════
        # 本地模式（保持原样）
        # ═══════════════════════════════════════════
        target_kb_dir = get_wiki_root(user_id) / kb_name
        if not target_kb_dir.exists():
            yield format_log(f"❌ 错误：在物理硬盘上未检测到目标沙箱路径: {target_kb_dir}")
            return

        yield format_log(f"🕷️ [LintFlow] 启动审查与织网流水线 | 🎯 锁定沙箱: [{kb_name}]")
        await asyncio.sleep(0.01)

        # 💡 路径自适应对齐：优先扫描核心 concepts 文件夹，不存在则降级根目录
        concepts_dir = target_kb_dir / "concepts"
        search_dir = concepts_dir if concepts_dir.exists() else target_kb_dir

        all_md_files = list(search_dir.rglob("*.md"))
        yield format_log(f"📂 在 [{kb_name}] 核心概念仓中发现 {len(all_md_files)} 个页面。")
        await asyncio.sleep(0.01)

        if not all_md_files:
            yield format_log("⚠️ 该沙箱概念仓为空，无需织网。")
            return

        # 记录映射表： target_concept -> set(source_file_names)
        backlinks_map = {}

        yield format_log("🔍 正在地毯式提取跨文件正向引用引用链...")
        await asyncio.sleep(0.01)

        for file_path in all_md_files:
            if file_path.name in ["index.md", "log.md"]:
                continue  # 跳过系统引导文件

            content = file_path.read_text(encoding="utf-8")
            source_name = file_path.stem

            # 找到当前文件里所有的 [[概念]] 和 [[别名|显示文本]]
            links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)

            for target in links:
                target_clean = target.strip()
                if not target_clean:
                    continue
                if target_clean not in backlinks_map:
                    backlinks_map[target_clean] = set()
                backlinks_map[target_clean].add(source_name)

        yield format_log(f"🕸️ 扫描完毕，累计发现 {len(backlinks_map)} 个处于引用状态的概念节点。")
        await asyncio.sleep(0.01)

        yield format_log("✍️ 正在自动进行反向链接 (Backlinks) 索引的物理写回...")
        await asyncio.sleep(0.01)

        updated_count = 0
        dead_links = []

        # 🔧 P0 优化：预构建归一化名称索引，O(N) 一次性扫描
        filename_index = {}
        for f in all_md_files:
            clean = f.stem.lower().replace("-", "").replace("_", "").replace(" ", "")
            filename_index[clean] = f

        for target_concept, sources in backlinks_map.items():
            # O(1) 索引查找替代 O(N) 暴力扫描
            clean_target = target_concept.lower().replace("-", "").replace("_", "").replace(" ", "")
            target_file = filename_index.get(clean_target)

            if not target_file:
                dead_links.append(target_concept)
                continue

            content = target_file.read_text(encoding="utf-8")

            # 构造要注入的反向链接字符串
            backlink_section = "\n## Backlinks\n"
            for src in sources:
                backlink_section += f"- [[{src}]]\n"

            # 简单剥离旧的 Backlinks 及之后的内容
            if "## Backlinks" in content:
                content = content.split("## Backlinks")[0].strip()

            # 追加新的反向链接
            new_content = content + "\n\n" + backlink_section
            target_file.write_text(new_content, encoding="utf-8")
            updated_count += 1

            yield format_log(f"  -> 🔗 成功重织反向链接节点: [{target_file.name}]")
            await asyncio.sleep(0.01)

        yield format_log(f"✅ 成功物理更新了 {updated_count} 个实体的拓扑索引！")
        await asyncio.sleep(0.01)

        if dead_links:
            dead_str = ", ".join(list(dead_links)[:5]) + (" ..." if len(dead_links) > 5 else "")
            yield format_log(f"⚠️ 核心警告：全库发现 {len(dead_links)} 个【幽灵死链】(有提及但在库中无文件): {dead_str}")
            await asyncio.sleep(0.01)

        # ═══ OKF: Staleness 检测 + 矛盾积压告警 ═══
        async for msg in self._okf_health_check_local(all_md_files, format_log):
            yield msg

        yield format_log(f"🕸️ [LintFlow] [{kb_name}] 织网完成，沙箱局部知识拓扑已彻底闭环！")

    # ═══════════════════════════════════════════
    # OKF: 知识库健康检查（staleness + 矛盾积压）
    # ═══════════════════════════════════════════

    async def _parse_frontmatter_timestamp(self, content: str):
        """从 OKF frontmatter 中提取 timestamp，返回 None 或 ISO 字符串"""
        if not content.startswith("---"):
            return None
        m = re.search(r'timestamp:\s*["\']?([^"\'\n]+)["\']?', content)
        return m.group(1).strip() if m else None

    async def _okf_health_check_minio(self, s, concept_keys, format_log):
        """MinIO 模式的健康检查"""
        now = datetime.datetime.now(datetime.timezone.utc)
        stale_90 = []
        stale_180 = []
        conflict_pages = []
        total_conflicts = 0

        for key in concept_keys:
            try:
                content = s.read_text(key)
            except Exception:
                continue
            name = key.split("/")[-1]

            ts = await self._parse_frontmatter_timestamp(content)
            if ts:
                try:
                    dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    days = (now - dt).days
                    if days > 180:
                        stale_180.append(f"{name} ({days}天)")
                    elif days > 90:
                        stale_90.append(f"{name} ({days}天)")
                except Exception:
                    pass

            conflict_count = content.count("## ⚠️ 矛盾待解决")
            if conflict_count:
                conflict_pages.append(f"{name} ({conflict_count}个)")
                total_conflicts += conflict_count

        async for msg in self._yield_health_results(stale_90, stale_180, conflict_pages, total_conflicts, format_log):
            yield msg

    async def _okf_health_check_local(self, md_files, format_log):
        """本地模式的健康检查"""
        now = datetime.datetime.now(datetime.timezone.utc)
        stale_90 = []
        stale_180 = []
        conflict_pages = []
        total_conflicts = 0

        for fp in md_files:
            if fp.name in ["index.md", "log.md", "schema.md"]:
                continue
            try:
                content = fp.read_text(encoding="utf-8")
            except Exception:
                continue
            name = fp.name

            ts = await self._parse_frontmatter_timestamp(content)
            if ts:
                try:
                    dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    days = (now - dt).days
                    if days > 180:
                        stale_180.append(f"{name} ({days}天)")
                    elif days > 90:
                        stale_90.append(f"{name} ({days}天)")
                except Exception:
                    pass

            conflict_count = content.count("## ⚠️ 矛盾待解决")
            if conflict_count:
                conflict_pages.append(f"{name} ({conflict_count}个)")
                total_conflicts += conflict_count

        async for msg in self._yield_health_results(stale_90, stale_180, conflict_pages, total_conflicts, format_log):
            yield msg

    async def _yield_health_results(self, stale_90, stale_180, conflict_pages, total_conflicts, format_log):
        """统一输出健康检查结果"""
        await asyncio.sleep(0.01)
        yield format_log("")
        yield format_log("═══ OKF 知识库健康报告 ═══")

        if stale_180:
            yield format_log(f"🔴 严重过期 (>180天): {', '.join(stale_180[:5])}")
            await asyncio.sleep(0.01)
        if stale_90:
            yield format_log(f"⚠️ 可能过期 (>90天): {', '.join(stale_90[:5])}")
            await asyncio.sleep(0.01)
        if not stale_90 and not stale_180:
            yield format_log("✅ 所有页面时效正常")
            await asyncio.sleep(0.01)

        if total_conflicts > 10:
            yield format_log(f"🔴 矛盾积压过多: 全库 {total_conflicts} 个未解决矛盾")
            await asyncio.sleep(0.01)
        elif conflict_pages:
            yield format_log(f"⚠️ 矛盾待解决: {', '.join(conflict_pages[:5])}")
            await asyncio.sleep(0.01)
        else:
            yield format_log("✅ 无积压矛盾")
            await asyncio.sleep(0.01)

    def _select_sandbox(self) -> Path:
        """保留单机 CLI 运行时的交互式终端菜单"""
        wiki_root = get_wiki_root()
        if not wiki_root.exists():
            print(f"❌ 根目录不存在: {wiki_root}")
            sys.exit(1)
        sandboxes = [d for d in wiki_root.iterdir() if d.is_dir()]
        if not sandboxes:
            print(f"❌ 在 {wiki_root} 下没有找到任何知识库沙箱。")
            sys.exit(1)

        print("\n" + "=" * 60)
        print("🗄️ 请选择要进行织网的知识库沙箱：")
        print("-" * 60)
        for i, kb in enumerate(sandboxes):
            print(f"  [{i}] {kb.name}")
        print("-" * 60)

        while True:
            choice = input("👉 请输入对应数字并回车 (输入 q 退出): ").strip()
            if choice.lower() == 'q':
                sys.exit(0)
            if choice.isdigit():
                idx = int(choice)
                if 0 <= idx < len(sandboxes):
                    return sandboxes[idx]
            print("⚠️ 输入无效，请输入正确的数字序号！")

    def run(self):
        """保留 CLI 单机脚本启动兼容入口"""
        target_kb_dir = self._select_sandbox()
        kb_name = target_kb_dir.name

        # 内部驱动同步运行打印
        async def run_cli():
            async for log in self.stream_run(kb_name):
                # 剥离 SSE 协议头，直接还原控制台输出
                clean_line = log.replace("data: ", "").strip()
                if clean_line:
                    try:
                        data = json.loads(clean_line)
                        print(data.get("content", ""))
                    except:
                        pass

        asyncio.run(run_cli())


if __name__ == "__main__":
    flow = LintFlow()
    flow.run()