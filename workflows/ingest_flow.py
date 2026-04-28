import json
import sys
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError
from agents.wiki_analyst import WikiAnalyst
from agents.wiki_writer import WikiWriter
from tools.document_parser import extract_text, chunk_text


class IngestFlow:
    """
    知识摄入流水线
    严格执行 Two-Step CoT（两步思维链）：先分析，后写入。
    """

    def __init__(self):
        self.analyst = WikiAnalyst()
        self.writer = WikiWriter()

    # 👇 就是这里！刚才报错就是因为它没被正确放进类里面
    def process_single_chunk(self, chunk, chunk_id):
        print(f"  [线程 {chunk_id}] 🧠 开始分析...")
        try:
            report = self.analyst.analyze(chunk)
            if not report.get("actions"):
                return chunk_id, None, "没有提取到核心概念"
            return chunk_id, report, "成功"
        except Exception as e:
            return chunk_id, None, f"报错: {str(e)}"

    def run(self, input_source: str):
        print("\n" + "=" * 60)
        print("🚀 [IngestFlow] 启动知识摄入流水线 (多线程提速版)...")

        path = Path(input_source)
        if path.exists() and path.is_file():
            print(f"📄 检测到文件：{path.name}")
            raw_text = extract_text(str(path))

            # ========================================================
            # 💡 动态上下文路由策略
            # ========================================================
            USE_CLOUD_LONG_CONTEXT = False

            if USE_CLOUD_LONG_CONTEXT:
                print("☁️ [架构路由] 开启全量沉浸式阅读 (1M Context)！")
                chunks = [raw_text]
                print(f"✂️ 文本共 {len(raw_text)} 字符，将进行一次性全局推理。")
            else:
                print("💻 [架构路由] 启用本地模型，激活滑动窗口切片策略。")
                chunks = chunk_text(raw_text, chunk_size=1500, overlap=200)
                print(f"✂️ 切分为 {len(chunks)} 个知识块 (Chunk Size: 1500)。")
            # ========================================================

        else:
            print("📝 检测到短文本输入。")
            chunks = [input_source]

        print("=" * 60)
        print("⚡ 启动并发处理引擎...")

        reports_to_write = []
        total_chunks = len(chunks)
        completed_count = 0

        with ThreadPoolExecutor(max_workers=12) as executor:
            futures = {executor.submit(self.process_single_chunk, chunk, i + 1): i for i, chunk in enumerate(chunks)}

            # 💡 兜底机制：加装“超时熔断器”
            try:
                # timeout=180 表示：如果整个监听过程有超过 3 分钟没有收到任何新回包，直接触发警报！
                for future in as_completed(futures, timeout=180):
                    completed_count += 1
                    chunk_id, report, status = future.result()

                    if report:
                        print(f"✅ [{completed_count}/{total_chunks}] 线程 {chunk_id} 分析完成，已存入待写队列。")
                        reports_to_write.append((chunk_id, report))
                    else:
                        print(f"⏭️ [{completed_count}/{total_chunks}] 线程 {chunk_id} 被跳过：{status}")
            except TimeoutError:
                # 💡 弃车保帅：一旦超时，立刻截断，拿着已有的成果继续往下走！
                print("\n⚠️ [兜底触发] 检测到 API 严重卡死或网络异常！")
                print(f"⚠️ 强行熔断！丢弃未响应的线程，强行结算已完成的 {len(reports_to_write)} 个知识块。")

        print("\n" + "=" * 60)
        print(f"✍️ 汇总完毕，准备执行物理写盘 (共 {len(reports_to_write)} 项任务)...")

        # 按照原来的顺序对结果进行排序，保证写入顺序的稳定性
        reports_to_write.sort(key=lambda x: x[0])

        for chunk_id, report in reports_to_write:
            self.writer.execute(report)

        print("\n" + "=" * 60)
        print("✅ [IngestFlow] 极速摄入完毕，完美收工！")
        print("=" * 60)


if __name__ == "__main__":
    import sys
    import os
    from pathlib import Path

    raw_dir = Path("data/raw")

    # 1. 安全检查：确保基础目录存在
    if not raw_dir.exists():
        raw_dir.mkdir(parents=True, exist_ok=True)
        print(f"⚠️ 找不到 {raw_dir} 目录，已为您自动创建。请先将数据放入该目录！")
        sys.exit(0)

    # 2. 自动扫描 data/raw 下的所有文件夹和独立的 PDF 文件
    items = [p for p in raw_dir.iterdir() if p.is_dir() or p.suffix.lower() == '.pdf']

    if not items:
        print(f"📭 {raw_dir} 目录下空空如也，请先放入包含论文或文档的文件夹。")
        sys.exit(0)

    # 3. 渲染 CLI 交互式菜单
    print("\n" + "=" * 50)
    print("🤖 欢迎使用 LLM-Wiki 自动化摄入系统")
    print("=" * 50)
    print("请选择要处理的知识源：\n")

    for i, item in enumerate(items, 1):
        icon = "📁" if item.is_dir() else "📄"
        print(f"  [{i}] {icon} {item.name}")
    print("\n" + "=" * 50)

    # 4. 获取用户输入
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

    # 5. 绑定目标并提取知识库名称
    input_target = items[choice_idx]
    kb_name = input_target.stem  # 直接用选中的文件夹/文件名作为隔离区名称

    os.environ["ACTIVE_KB"] = kb_name
    print(f"\n🌐 [系统路由] 自动提取并激活知识隔离区: {kb_name}")

    # 6. 初始化并执行流水线
    flow = IngestFlow()

    # 7. 智能判断与递归路由执行
    if input_target.is_file():
        os.environ["ACTIVE_SUBDIR"] = ""
        # 💡 新增：把单文件的纯名字作为容器名
        os.environ["ACTIVE_DOC_NAME"] = input_target.stem
        flow.run(str(input_target))

    elif input_target.is_dir():
        files = list(input_target.rglob("*.pdf"))
        print(f"📂 开始深度扫描 [{input_target.name}]，共发现 {len(files)} 个文档。")

        for idx, file_path in enumerate(files, 1):
            # 计算相对子目录，用于给底层的 _resolve 提供路径
            if file_path.parent == input_target:
                rel_dir = ""
            else:
                rel_dir = str(file_path.parent.relative_to(input_target))

            os.environ["ACTIVE_SUBDIR"] = rel_dir
            # 💡 新增：把当前遍历到的 PDF 名字作为容器名注入！
            os.environ["ACTIVE_DOC_NAME"] = file_path.stem

            print("\n" + "-" * 50)
            print(f"🚀 [批量进度 {idx}/{len(files)}] 正在解析: {file_path.name}")

            # 💡 优化了日志输出，让你提前看到极其舒适的目录结构
            display_dir = f"{kb_name}/{rel_dir}/{file_path.stem}" if rel_dir else f"{kb_name}/{file_path.stem}"
            print(f"📁 物理落库路径: data/wiki/{display_dir}/")

            flow.run(str(file_path))