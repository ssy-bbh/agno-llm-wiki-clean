import sys
import os
import re
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

from agents.wiki_analyst import WikiAnalyst
from agents.wiki_editor import WikiEditor
from agents.wiki_writer import WikiWriter
from tools.document_parser import extract_text, chunk_text
from tools.edit_tools import _resolve, set_context, _resolve_key
from core.storage import get_storage
from core.path_resolver import USE_MINIO
from core.path_resolver import minio_concepts_prefix, minio_index_key
from core.ingest_control import (
    is_terminate_requested, mark_concept_done,
    is_concept_done, save_file_checkpoint, save_shuffle_result,
)


class IngestFlow:
    """
    知识摄入流水线 (终极形态：Map-Reduce 降维打击版)
    """

    def __init__(self):
        self.analyst = WikiAnalyst()
        self.writer = WikiWriter()
        # Editor 会在循环内动态实例化，防止上下文记忆污染

        # ═══ P0 优化：缓存与索引 ═══
        self._file_cache = {}           # {filepath: content} 文件内容缓存
        self._context_cache = {}        # {concept_tuple: context_str} 上下文缓存
        self._concept_index = {}        # {normalized_name: Path} 概念文件索引

    def _normalize_name(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', text).lower()

    def _build_concept_index(self):
        """🔧 P0-1: 一次性构建概念文件索引，后续查找 O(1)"""
        index = {}
        if USE_MINIO:
            s = get_storage()
            from tools.edit_tools import get_context
            ctx = get_context()
            prefix = minio_concepts_prefix(ctx["user_id"], ctx["kb_name"])
            all_keys = get_storage().list_keys(prefix)
            for key in all_keys:
                if key.endswith(".md"):
                    stem = key.split("/")[-1].replace(".md", "")
                    norm = self._normalize_name(stem)
                    if norm:
                        index[norm] = key  # MinIO key 字符串
        else:
            concepts_dir = _resolve("concepts")
            if concepts_dir.exists():
                for f in concepts_dir.glob("*.md"):
                    norm = self._normalize_name(f.stem)
                    if norm:
                        index[norm] = f  # 本地 Path 对象
        self._concept_index = index
        print(f"  📇 概念索引已构建: {len(index)} 个文件")

    def _find_existing_file(self, concept: str) -> Path:
        """同义词嗅探器：基于预构建索引 O(1) 查找，回退模糊匹配"""
        norm_c = self._normalize_name(concept)
        if not norm_c:
            return None

        # O(1) 精确命中
        if norm_c in self._concept_index:
            return self._concept_index[norm_c]

        # O(N) 模糊包含匹配（仅对短索引回退）
        if len(norm_c) > 2:
            for norm_f, f in self._concept_index.items():
                if len(norm_f) > 2:
                    if norm_c in norm_f or norm_f in norm_c:
                        return f
        return None

    def _read_file_cached(self, filepath) -> str:
        """🔧 P0-2: 带缓存的文件读取，同一批次内不重复读盘"""
        key = str(filepath)
        if key not in self._file_cache:
            if USE_MINIO and not isinstance(filepath, Path):
                # MinIO 模式：filepath 是 MinIO key 字符串
                self._file_cache[key] = get_storage().read_text(filepath)
            else:
                # 本地模式：filepath 是 Path 对象
                self._file_cache[key] = filepath.read_text(encoding="utf-8")
        return self._file_cache[key]

    def _fetch_local_context(self, concepts: list) -> str:
        """档案管理员：提取上下文，提供给大模型参考（带缓存）
        
        💡 Token 瘦身：只传 index.md 标题列表 + 概念文件 Abstract 段，不传全文。
           Editor 需要知道「哪些概念存在」和「大概是什么」，不需要读全文做融合。
        """
        cache_key = tuple(sorted(concepts))
        if cache_key in self._context_cache:
            return self._context_cache[cache_key]

        context_str = "\n"

        if USE_MINIO:
            s = get_storage()
            from tools.edit_tools import get_context
            ctx = get_context()
            idx_key = minio_index_key(ctx["user_id"], ctx["kb_name"])

            if get_storage().exists(idx_key):
                full = self._read_file_cached(idx_key)
                if len(full) > 8000:
                    toc_lines = [l for l in full.split('\n') if l.strip().startswith('#') or (l.strip().startswith('-') and '[[' in l)]
                    toc = '\n'.join(toc_lines[:200]) if toc_lines else full[:3000]
                    context_str += f"=== index.md (导航地图，已截断) ===\n{toc}\n\n"
                else:
                    context_str += f"=== index.md (导航地图) ===\n{full}\n\n"
            else:
                context_str += "=== index.md (导航地图) ===\n(文件不存在)\n\n"

            for concept in concepts:
                existing_key = self._find_existing_file(concept)
                if existing_key:
                    content = self._read_file_cached(existing_key)
                    file_name = existing_key.split("/")[-1]
                    rel_path = f"concepts/{file_name}"
                    # 📉 只传 Abstract 段（~300字），不传全文（~3000字）
                    abstract = self._extract_abstract(content)
                    context_str += f"=== {rel_path} (摘要) ===\n{abstract}\n\n"
                else:
                    safe_name = concept.replace("/", "_").replace("\\", "_").replace(":", "_").replace("?", "_")
                    context_str += f"=== concepts/{safe_name}.md ===\n(全新概念)\n\n"
        else:
            index_path = _resolve("index.md")

            if index_path.exists():
                full = self._read_file_cached(index_path)
                if len(full) > 8000:
                    toc_lines = [l for l in full.split('\n') if l.strip().startswith('#') or (l.strip().startswith('-') and '[[' in l)]
                    toc = '\n'.join(toc_lines[:200]) if toc_lines else full[:3000]
                    context_str += f"=== index.md (导航地图，已截断) ===\n{toc}\n\n"
                else:
                    context_str += f"=== index.md (导航地图) ===\n{full}\n\n"
            else:
                context_str += "=== index.md (导航地图) ===\n(文件不存在)\n\n"

            for concept in concepts:
                real_file = self._find_existing_file(concept)
                if real_file:
                    content = self._read_file_cached(real_file)
                    rel_path = f"concepts/{real_file.name}"
                    # 📉 只传 Abstract 段（~300字），不传全文（~3000字）
                    abstract = self._extract_abstract(content)
                    context_str += f"=== {rel_path} (摘要) ===\n{abstract}\n\n"
                else:
                    safe_name = concept.replace("/", "_").replace("\\", "_").replace(":", "_").replace("?", "_")
                    context_str += f"=== concepts/{safe_name}.md ===\n(全新概念)\n\n"

        self._context_cache[cache_key] = context_str
        return context_str

    @staticmethod
    def _extract_abstract(content: str) -> str:
        """从概念页中提取 Abstract 段摘要（~300字），避免传全文给 LLM"""
        # 优先提取 ## Abstract 到下一个 ## 之间的内容
        if "## Abstract" in content:
            after = content.split("## Abstract", 1)[1]
            # 截断到下一个 ## 标题
            if "\n## " in after:
                after = after.split("\n## ", 1)[0]
            return after.strip()[:500]
        # 回退：取前 300 字
        return content[:300]

    def _map_extract(self, chunk, chunk_id):
        """Map 阶段的核心逻辑：只提取，不写盘"""
        try:
            if hasattr(self, '_skip_map') and self._skip_map:
                return 0, chunk, None, "resume-skip"
            print(f"  [Map 线程 {chunk_id}] 🕵️‍♂️ 提取中...")
            analysis_result = self.analyst.analyze(chunk)
            if not analysis_result.get("new_concepts"):
                return chunk_id, chunk, None, "无核心概念"
            return chunk_id, chunk, analysis_result, "成功"
        except Exception as e:
            return chunk_id, chunk, None, f"报错: {str(e)}"

    def run(self, input_source: str, kb_name: str = "", user_id: str = "", doc_name: str = "", pending_payloads: dict = None):
        """
        知识摄入入口。
        kb_name: 目标沙箱名称（通过参数传递，避免 os.environ 竞态）
        user_id: 用户 ID（用于路径隔离）
        doc_name: 原始文档名（MinIO 模式下传入，避免使用临时文件名）
        """
        # 在调用任何 _resolve 前，设置线程安全上下文
        set_context(user_id=user_id, kb_name=kb_name or "default", sub_dir="")

        # 早期终止检查：还没开始重活之前快速退出
        if user_id and kb_name and is_terminate_requested(user_id, kb_name):
            print(f"\n🛑 [IngestFlow] 收到终止信号，跳过 {Path(input_source).name}")
            return False  # 返回 False 表示被终止
        # 在调用任何 _resolve 前，设置线程安全上下文
        set_context(user_id=user_id, kb_name=kb_name or "default", sub_dir="")

        # ── Resume 快速路径标记 ──
        _pending = pending_payloads  # None = 正常模式，dict = resume 模式

        print("\n" + "=" * 60)
        print(f"🚀 [IngestFlow] 启动 Map-Reduce 引擎 | 沙箱: {kb_name} | 用户: {user_id}")

        # 设置文档名到上下文
        path = Path(input_source)
        if path.exists() and path.is_file():
            # ── 单文件模式 ──
            _doc = doc_name or path.stem
            set_context(user_id=user_id, kb_name=kb_name or "default", sub_dir="", doc_name=_doc)
            print(f"📄 目标语料：{_doc} ({path.stat().st_size} bytes)", flush=True)
            try:
                raw_text = extract_text(str(path))
            except Exception as e:
                print(f"❌ extract_text 失败: {type(e).__name__}: {e}", flush=True)
                raw_text = ""
            print(f"📝 提取文本: {len(raw_text)} 字符", flush=True)
            if not raw_text.strip():
                print("⚠️ 警告：提取出的文本为空！PDF 可能是扫描图片（需要 OCR）或文件损坏。", flush=True)
            chunks = chunk_text(raw_text, chunk_size=1500, overlap=200)
            print(f"✂️ 物理切分为 {len(chunks)} 个知识块。", flush=True)
        elif path.exists() and path.is_dir():
            # ── 目录模式：遍历所有文件，合并文本后切块 ──
            SUPPORTED_EXT = {".pdf", ".docx", ".md", ".txt"}
            all_text = ""
            file_count = 0
            for file in sorted(path.iterdir()):
                if file.is_file() and file.suffix.lower() in SUPPORTED_EXT:
                    try:
                        text = extract_text(str(file))
                        if text.strip():
                            all_text += f"\n\n--- [{file.name}] ---\n\n" + text
                            file_count += 1
                            print(f"  📄 读取: {file.name} ({len(text)} 字符)")
                    except Exception as e:
                        print(f"  ⚠️ 跳过 {file.name}: {e}")
            if not all_text.strip():
                print("❌ 目录中没有可解析的文件")
                chunks = []
            else:
                print(f"📚 共读取 {file_count} 个文件 ({len(all_text)} 字符)")
                chunks = chunk_text(all_text, chunk_size=1500, overlap=200)
                print(f"✂️ 物理切分为 {len(chunks)} 个知识块。")
        else:
            # 兜底：把 input_source 当原始文本
            chunks = chunk_text(input_source, chunk_size=1500, overlap=200)
            print(f"✂️ 原始文本切分为 {len(chunks)} 个知识块。")

        # ==========================================
        # 🟢 PHASE 1: MAP (无锁绝对并发)
        # ==========================================
        map_lock = threading.Lock()
        self._skip_map = bool(_pending)  # resume skip

        print("\n" + "=" * 60)
        print("⚡ [Phase 1: MAP] 启动侦察兵并发提取 (释放全部线程)...")

        map_results = []
        # 使用 12 个并发线程进行提取
        with ThreadPoolExecutor(max_workers=12) as executor:
            futures = {executor.submit(self._map_extract, chunk, i + 1): i for i, chunk in enumerate(chunks)}

            for future in as_completed(futures):
                cid, chunk_text_val, res, status = future.result()
                if res:
                    # 进入临界区，安全写入内存
                    with map_lock:
                        map_results.append((chunk_text_val, res))
                    print(f"  -> ✅ 线程 {cid} 提取完毕: {res.get('new_concepts')}")

        # ==========================================
        # 🟡 PHASE 2: SHUFFLE (内存级同义词聚类)
        # ==========================================
        print("\n" + "=" * 60)
        print("🔀 [Phase 2: SHUFFLE] 正在将碎片知识按概念重新洗牌聚类 (启动双语解构引擎)...")

        concept_payloads = {}
        for chunk_text_val, res in map_results:
            concepts = res.get("new_concepts", [])
            summary = res.get("summary", "")

            for raw_c in concepts:
                # 尝试剥离 "English (中文)" 格式
                match = re.match(r'^(.*?)\s*[\(（](.*?)[\)）]', raw_c)
                if match:
                    en_key = match.group(1).strip()
                    zh_alias = match.group(2).strip()
                    full_display = f"{en_key} ({zh_alias})"
                else:
                    en_key = raw_c.strip()
                    zh_alias = ""
                    full_display = en_key

                # 过滤明显不是概念的超长垃圾数据
                if len(en_key.split()) > 4 or len(en_key) > 25:
                    continue

                norm_c = self._normalize_name(en_key)
                if not norm_c or len(norm_c) < 2:
                    continue

                if norm_c not in concept_payloads:
                    concept_payloads[norm_c] = {
                        "primary_key": en_key,
                        "display_name": full_display,
                        "aliases": set(),
                        "texts": [],
                        "summaries": []
                    }

                if zh_alias:
                    concept_payloads[norm_c]["aliases"].add(zh_alias)

                concept_payloads[norm_c]["texts"].append(chunk_text_val)
                concept_payloads[norm_c]["summaries"].append(summary)

        # 📉 SHUFFLE 低频过滤：动态阈值，短文宽容、长文严格
        total_chunks = len(map_results)
        min_mentions = 2 if total_chunks >= 10 else 1
        before_filter = len(concept_payloads)
        concept_payloads = {
            k: v for k, v in concept_payloads.items()
            if len(v["texts"]) >= min_mentions
        }
        filtered = before_filter - len(concept_payloads)
        if filtered:
            print(f"  🗑️ 过滤低频概念: {filtered} 个（提及 < {min_mentions} 次，总 {total_chunks} 个 chunk）")

        # 保存 SHUFFLE 结果到检查点缓存（供 resume 跳过 MAP+SHUFFLE）
        if user_id and kb_name and not _pending:
            _fn = doc_name or (path.name if path.exists() else str(input_source))
            save_shuffle_result(user_id, kb_name, _fn, concept_payloads)

        # Resume 覆盖：如果有 pending_payloads，替换 SHUFFLE 的空结果
        if _pending is not None:
            concept_payloads = _pending
            print(f"  📦 [RESUME] 使用缓存的 SHUFFLE 结果: {len(concept_payloads)} 个概念")

        # ==========================================
        # 🔴 PHASE 3: REDUCE (串行概念融合)
        # ==========================================
        print("\n" + "=" * 60)
        total_concepts = len(concept_payloads)
        print(f"🧠 [Phase 3: REDUCE] 惊人降维！发现 {total_concepts} 个独立核心概念。")

        # 🔧 P0-1: 预构建概念索引（O(N) 一次性扫描，后续查找 O(1)）
        self._build_concept_index()

        # 🔧 P0-2: 清空缓存（新批次，防止旧数据干扰）
        self._file_cache.clear()
        self._context_cache.clear()

        t_reduce_start = time.time()

        skipped_count = 0
        error_count = 0
        checkpoint_count = 0  # 从检查点跳过的概念数
        terminated = False
        reduce_pool = ThreadPoolExecutor(max_workers=1)

        for seq, (norm_c, payload) in enumerate(concept_payloads.items(), 1):
            display_name = payload["display_name"]

            # ── 终止检查（每个概念开始前）──
            if user_id and kb_name and is_terminate_requested(user_id, kb_name):
                print(f"\n🛑 [REDUCE] 收到终止信号，在概念 {seq}/{total_concepts} 前停止")
                terminated = True
                break

            # ── 检查点跳过（Resume 时已处理的概念不再重复调 LLM）──
            if user_id and kb_name and is_concept_done(user_id, kb_name, norm_c):
                checkpoint_count += 1
                print(f"  ⏩ [{seq}/{total_concepts}] [{display_name}] 已在检查点中，跳过")
                continue

            print(f"  🔄 [融合 {seq}/{total_concepts}] 目标概念: [{display_name}]")
            t0 = time.time()

            combined_text = "\n\n... (接上文补充资料) ...\n\n".join(payload["texts"])

            # Token 熔断保护
            MAX_CHARS = 8000
            if len(combined_text) > MAX_CHARS:
                print(f"  -> ⚠️ [{display_name}] 过长 ({len(combined_text)} 字符)，已截断")
                combined_text = combined_text[:MAX_CHARS] + "\n\n... [数据过长，出于系统上下文保护已截断，请基于以上核心信息进行融合] ..."

            combined_summary = "\n".join(payload["summaries"])
            existing_context = self._fetch_local_context([display_name])

            # ── 可中断的 LLM 调用 ──
            _merge_uid, _merge_kb = user_id, kb_name
            def _do_merge():
                set_context(user_id=_merge_uid, kb_name=_merge_kb or "default", sub_dir="")
                return WikiEditor().merge(
                    raw_text=combined_text,
                    analyst_summary=combined_summary,
                    existing_context=existing_context
                )
            try:
                merge_future = reduce_pool.submit(_do_merge)
                while not merge_future.done():
                    if user_id and kb_name and is_terminate_requested(user_id, kb_name):
                        terminated = True
                        break
                    try:
                        merge_future.result(timeout=0.5)
                    except FuturesTimeoutError:
                        continue
                if terminated:
                    # ── 优雅终止：如果当前融合已完成，先保存结果再退出 ──
                    if merge_future.done():
                        try:
                            report = merge_future.result(timeout=0)
                            if report and report.get("actions"):
                                self.writer.execute(report)
                                if user_id and kb_name:
                                    mark_concept_done(user_id, kb_name, norm_c)
                                elapsed = time.time() - t0
                                print(f"  -> ✅ [{display_name}] 融合完毕 ({elapsed:.1f}s)（终止前抢救完成）")
                        except Exception as e:
                            print(f"  -> ⚠️ [{display_name}] 终止时保存结果失败: {e}")
                    reduce_pool.shutdown(wait=False)
                    break
                report = merge_future.result()

                if report and report.get("actions"):
                    self.writer.execute(report)
                else:
                    print(f"  -> 🔔 主编裁定: [{display_name}] 无实质增量信息，跳过写盘。")
                    skipped_count += 1

                # ── 保存检查点（融合成功后立即记录，从待处理列表移除）──
                if user_id and kb_name:
                    mark_concept_done(user_id, kb_name, norm_c)

                elapsed = time.time() - t0
                print(f"  -> ✅ [{display_name}] 融合完毕 ({elapsed:.1f}s)")

            except Exception as e:
                elapsed = time.time() - t0
                error_count += 1
                print(f"  -> ❌ 合并 [{display_name}] 时发生致命错误: {e}")
        t_total = time.time() - t_reduce_start
        print("\n" + "=" * 60)
        stats_parts = [f"REDUCE 耗时: {t_total:.1f}s"]
        if checkpoint_count:
            stats_parts.append(f"检查点跳过: {checkpoint_count}")
        if skipped_count:
            stats_parts.append(f"无增量: {skipped_count}")
        if error_count:
            stats_parts.append(f"失败: {error_count}")
        if terminated:
            stats_parts.append("⚠️ 用户终止")
        print(f"✅ [IngestFlow] 文件处理完成 | {' | '.join(stats_parts)} | 知识图谱已延展！")

        # 返回是否被终止（供外层循环判断）
        return not terminated


if __name__ == "__main__":
    # 自动定位项目根目录（支持从项目根或 workflows/ 子目录运行）
    _script_dir = Path(__file__).resolve().parent
    _project_root = _script_dir.parent if _script_dir.name == "workflows" else _script_dir
    raw_dir = _project_root / "data" / "raw"

    if not raw_dir.exists():
        raw_dir.mkdir(parents=True, exist_ok=True)
        print(f"⚠️ 找不到 {raw_dir} 目录，已为您自动创建。请先将数据放入该目录！")
        sys.exit(0)

    # 读取 raw/ 下的所有文件夹（作为沙箱）和 PDF
    items = [p for p in raw_dir.iterdir() if p.is_dir() or p.suffix.lower() == '.pdf']

    if not items:
        print(f"📭 {raw_dir} 目录下空空如也，请先放入包含论文或文档的文件夹。")
        sys.exit(0)

    print("\n" + "=" * 50)
    print("🤖 欢迎使用 LLM-Wiki 本地自动化摄入系统")
    print("=" * 50)
    print("请选择要处理的知识源：\n")

    for i, item in enumerate(items, 1):
        icon = "🗂️" if item.is_dir() else "📄"
        print(f"  [{i}] {icon} {item.name}")
    print("\n" + "=" * 50)

    try:
        choice = input("👉 请输入对应编号 (按 Ctrl+C 退出): ").strip()
        choice_idx = int(choice) - 1
        if choice_idx < 0 or choice_idx >= len(items):
            raise ValueError
    except (ValueError, IndexError):
        print("❌ 输入无效，请输入正确的数字编号。")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 已取消操作。")
        sys.exit(0)

    input_target = items[choice_idx]
    flow = IngestFlow()

    # 💡 核心逻辑适配：如果选择了文件夹，则文件夹名即为专属沙箱名
    if input_target.is_dir():
        files = list(input_target.rglob("*.pdf"))
        print(f"📂 开始深度扫描沙箱文件夹 [{input_target.name}]，共发现 {len(files)} 份语料。")

        # 锁定沙箱名
        kb_name = input_target.stem
        set_context(kb_name=kb_name)
        print(f"📁 知识流向: 锁定专属沙箱 -> [data/wiki/{kb_name}/]")

        for idx, file_path in enumerate(files, 1):
            set_context(kb_name=kb_name, doc_name=file_path.stem)

            print("\n" + "-" * 50)
            print(f"🚀 [批量进度 {idx}/{len(files)}] 正在解析: {file_path.name}")
            flow.run(str(file_path), kb_name=kb_name)

        print(f"\n✅✅ 沙箱 [{kb_name}] 的批量提炼任务已全部完成！")

    # 如果选择了单个文件，则自动以文件名开辟新沙箱
    elif input_target.is_file():
        kb_name = input_target.stem
        set_context(kb_name=kb_name, doc_name=input_target.stem)

        print(f"\n📁 知识流向: 为该文件单独开辟沙箱 -> [data/wiki/{kb_name}/]")
        flow.run(str(input_target), kb_name=kb_name)