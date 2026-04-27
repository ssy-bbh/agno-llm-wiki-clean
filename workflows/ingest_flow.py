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
                chunks = chunk_text(raw_text, chunk_size=4000, overlap=400)
                print(f"✂️ 切分为 {len(chunks)} 个知识块 (Chunk Size: 4000)。")
            # ========================================================

        else:
            print("📝 检测到短文本输入。")
            chunks = [input_source]

        print("=" * 60)
        print("⚡ 启动并发处理引擎...")

        reports_to_write = []
        total_chunks = len(chunks)
        completed_count = 0

        with ThreadPoolExecutor(max_workers=5) as executor:
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
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    if len(sys.argv) > 1:
        text_to_ingest = " ".join(sys.argv[1:])
    else:
        text_to_ingest = "今天了解到一种叫 RAG 的技术..."

    flow = IngestFlow()
    flow.run(text_to_ingest)