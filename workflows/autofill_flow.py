"""
autofill_flow.py - 幽灵节点实例化引擎 (知识黑洞自动填补)
v2: 全程直操 MinIO，不经过本地文件系统
"""
import os
import re
import json
import asyncio
from collections import Counter

from agents.wiki_editor import WikiEditor

# MinIO 直操
from core.storage import get_client, BUCKET, read as minio_read, write as minio_write, list_keys


def _normalize_name(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', text).lower()


def _safe_title(title: str) -> str:
    """与 WikiWriter 一致的标题净化"""
    return title.replace("/", "_").replace("\\", "_").replace(":", "_").replace("?", "_")


def _is_same_concept(name1: str, name2: str) -> bool:
    """同义词防撞雷达（与 WikiWriter 一致）"""
    def _get_aliases(text: str) -> set:
        aliases = set()
        clean_text = text.lower().replace("-", "").replace("_", "").replace(" ", "")
        if clean_text:
            aliases.add(clean_text)
        match = re.match(r'^(.*?)\s*[\(（](.*?)[\)）]', text)
        if match:
            p1 = match.group(1).lower().replace("-", "").replace("_", "").replace(" ", "")
            p2 = match.group(2).lower().replace("-", "").replace("_", "").replace(" ", "")
            if p1: aliases.add(p1)
            if p2: aliases.add(p2)
        return aliases
    return bool(_get_aliases(name1) & _get_aliases(name2))


class AutoFillFlow:
    def __init__(self, threshold: int = 5):
        self.threshold = threshold

    async def stream_run(self, kb_name: str, user_id: str = ""):
        """全程 MinIO 直操版"""

        def fmt(msg):
            return f"data: {json.dumps({'type': 'log', 'content': msg})}\n\n"

        yield fmt(f"🕳️ [AutoFill v2] 启动知识黑洞探测 | 🎯 沙箱: {kb_name} | ☁️ 直操 MinIO")
        await asyncio.sleep(0.01)

        prefix = f"wiki/{user_id}/{kb_name}/concepts"
        DRAFT_TAG = "<!-- AUTOFILL_DRAFT -->"
        client = get_client()

        # ═══════════════════════════════════════
        # 1. 从 MinIO 读取所有概念文件
        # ═══════════════════════════════════════
        all_keys = [k for k in list_keys(prefix) if k.endswith(".md")]
        if not all_keys:
            yield fmt("❌ MinIO 中 concepts 为空，图谱无数据，无法探测。")
            return

        yield fmt(f"📡 从 MinIO 加载 {len(all_keys)} 个概念文件...")
        await asyncio.sleep(0.01)

        # key → (filename, content)
        files = {}  # {filename: content}
        key_map = {}  # {filename: minio_key}
        for key in all_keys:
            fname = key[len(prefix):].lstrip("/")
            if not fname:
                continue
            try:
                content = minio_read(key)
                files[fname] = content
                key_map[fname] = key
            except Exception as e:
                print(f"  ⚠️ MinIO 读取失败 {key}: {e}", flush=True)

        # ═══════════════════════════════════════
        # 2. 扫描链接 + 统计入度
        # ═══════════════════════════════════════
        link_counter = Counter()
        backlinks = {}  # {link_name: [source_filenames]}

        for fname, content in files.items():
            links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)
            stem = fname.replace(".md", "")
            for link in links:
                clean = link.strip()
                if not clean:
                    continue
                link_counter[clean] += 1
                if clean not in backlinks:
                    backlinks[clean] = []
                if stem not in backlinks[clean]:
                    backlinks[clean].append(stem)

        # ═══════════════════════════════════════
        # 3. 别名匹配 + 偷天换日（直接写回 MinIO）
        # ═══════════════════════════════════════
        existing_stems = [f.replace(".md", "") for f in files.keys()]
        target_ghosts = []

        yield fmt("🛠️ [自愈系统] 清理异名同义假空节点...")
        await asyncio.sleep(0.01)

        for link, count in link_counter.items():
            # 尝试匹配已有文件
            real_target = None
            for stem in existing_stems:
                if _is_same_concept(link, stem):
                    real_target = stem
                    break

            if real_target:
                if link != real_target:
                    yield fmt(f"  -> 🔀 [偷天换日] [{link}] -> [{real_target}]")
                    await asyncio.sleep(0.01)
                    # 修复所有引用了假链接的源文件
                    for source_stem in backlinks.get(link, []):
                        source_fname = f"{source_stem}.md"
                        if source_fname in files:
                            content = files[source_fname]
                            pattern = re.compile(rf'\[\[{re.escape(link)}(?:\|([^\]]+))?\]\]')
                            new_content = pattern.sub(
                                lambda m: f"[[{real_target}|{m.group(1) or link}]]", content
                            )
                            if new_content != content:
                                # 直接写回 MinIO
                                files[source_fname] = new_content  # 更新内存
                                try:
                                    minio_write(key_map[source_fname], new_content)
                                    print(f"  [AutoFill v2] ✅ MinIO 链接修复: {source_fname}", flush=True)
                                except Exception as e:
                                    print(f"  [AutoFill v2] ⚠️ MinIO 写回失败 {source_fname}: {e}", flush=True)
            else:
                if count >= self.threshold:
                    target_ghosts.append((link, count))

        target_ghosts.sort(key=lambda x: x[1], reverse=True)

        if not target_ghosts:
            yield fmt("✅ 图谱健康，未发现触发阈值的真空黑洞。")
            return

        yield fmt(f"🎯 探测到 {len(target_ghosts)} 个高频真空节点 (≥{self.threshold}次引用):")
        await asyncio.sleep(0.01)

        # ═══════════════════════════════════════
        # 4. 逐个填补 — LLM 生成 → 直写 MinIO
        # ═══════════════════════════════════════
        yield fmt("🪄 启动 WikiEditor 智能体合成实体，直接写入 MinIO...")
        await asyncio.sleep(0.01)

        for node, count in target_ghosts:
            yield fmt(f"✨ [实例化中] 合成: [{node}] (被引用 {count} 次)")
            await asyncio.sleep(0.01)

            # 构建上下文
            source_docs = ""
            for source_stem in backlinks.get(node, [])[:3]:
                source_fname = f"{source_stem}.md"
                if source_fname in files:
                    snippet = files[source_fname][:600]
                    source_docs += f"\n=== {source_stem} (提及了该概念) ===\n{snippet}...\n"

            prompt_text = (
                f"你是一个知识图谱修复专家。目前系统内有一个核心概念【{node}】被多次引用,"
                f"但其独立条目缺失。请基于你的通用知识，以及下面提供的关联文档上下文，"
                f"直接生成关于【{node}】的详细百科解释。\n\n"
                f"关联上下文参考:\n{source_docs}"
            )

            try:
                editor = WikiEditor()
                report = editor.merge(
                    raw_text=prompt_text,
                    analyst_summary=f"这是一个高频核心实体,必须创建一个全新的详细词条:{node}",
                    existing_context=f"=== concepts/{node}.md ===\n(全新概念,待你创建)\n"
                )

                if not report or not report.get("actions"):
                    yield fmt(f"  -> ⏭️ 智能主编拒绝生成: [{node}]")
                    continue

                # 解析 actions，提取要创建的内容
                created = 0
                for action in report["actions"]:
                    act_type = action.get("type")
                    if act_type == "create":
                        title = (action.get("title") or node).strip()
                        safe = _safe_title(title)
                        content = action.get("content", "").replace("\\n", "\n")

                        # 冲突检测：MinIO 中是否已有同义词文件
                        conflict = False
                        for existing_stem in existing_stems:
                            if _is_same_concept(existing_stem, title):
                                # 已有同义词 → 追加模式
                                existing_fname = f"{existing_stem}.md"
                                if existing_fname in files:
                                    append_content = f"\n\n---\n### 🧠 增量融合视角 ({title})\n{content}\n"
                                    merged = files[existing_fname] + append_content
                                    files[existing_fname] = merged
                                    try:
                                        minio_write(key_map[existing_fname], merged)
                                        print(f"  [AutoFill v2] ✅ 追加到已有文件: {existing_fname}", flush=True)
                                    except Exception as e:
                                        print(f"  [AutoFill v2] ⚠️ 追加写回失败: {e}", flush=True)
                                    conflict = True
                                    break

                        if not conflict:
                            # 全新创建 → 加 DRAFT_TAG → 直写 MinIO
                            new_fname = f"{safe}.md"
                            new_key = f"{prefix}/{new_fname}"
                            tagged_content = DRAFT_TAG + "\n" + content
                            try:
                                minio_write(new_key, tagged_content)
                                files[new_fname] = tagged_content
                                key_map[new_fname] = new_key
                                existing_stems.append(safe)
                                created += 1
                                print(f"  [AutoFill v2] ✅ DRAFT 直写 MinIO: {new_fname}", flush=True)
                            except Exception as e:
                                print(f"  [AutoFill v2] ❌ MinIO 写入失败 {new_fname}: {e}", flush=True)

                    elif act_type in ("edit", "str_replace"):
                        # 编辑已有文件 — 直接操作 MinIO
                        raw_file = action.get("file", "")
                        if not raw_file.startswith("concepts/"):
                            raw_file = f"concepts/{raw_file}"
                        fname = raw_file.replace("concepts/", "")
                        if fname in files:
                            content = files[fname]
                            old_str = action.get("old_str", "")
                            new_str = action.get("new_str", "")
                            if old_str and old_str in content:
                                content = content.replace(old_str, new_str, 1)
                                files[fname] = content
                                try:
                                    minio_write(key_map[fname], content)
                                    print(f"  [AutoFill v2] ✅ MinIO 编辑: {fname}", flush=True)
                                except Exception as e:
                                    print(f"  [AutoFill v2] ⚠️ 编辑写回失败: {e}", flush=True)

                if created > 0:
                    yield fmt(f"  -> 📝 生成 {created} 个草稿，已送入 Inbox 待审")
                else:
                    yield fmt(f"  -> 📝 WikiEditor 执行完成（可能合并到已有文件）")

            except Exception as e:
                yield fmt(f"  -> ❌ 填补 [{node}] 异常: {e}")
                print(f"  [AutoFill v2] ERROR: {e}", flush=True)

        yield fmt("✅ [AutoFill v2] 全部完成！黑洞已填补，数据直写 MinIO。")

    def run(self):
        """保留单机终端调试兼容性"""
        from pathlib import Path
        wiki_dir = Path(__file__).resolve().parent.parent / "data" / "wiki"
        if not wiki_dir.exists():
            return
        kbs = [p for p in wiki_dir.iterdir() if p.is_dir()]
        if not kbs:
            return
        print("\n📂 请选择本地沙箱:")
        for i, kb in enumerate(kbs, 1):
            print(f"  [{i}] {kb.name}")
        choice = input("👉 输入编号: ").strip()
        selected_kb = kbs[int(choice) - 1].name

        async def run_cli():
            async for log in self.stream_run(selected_kb):
                clean = log.replace("data: ", "").strip()
                if clean:
                    try:
                        print(json.loads(clean).get("content", ""))
                    except:
                        pass
        asyncio.run(run_cli())


if __name__ == "__main__":
    flow = AutoFillFlow(threshold=5)
    flow.run()
