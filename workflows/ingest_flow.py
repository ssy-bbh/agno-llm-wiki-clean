"""
ingest_flow.py — 摄入流水线
严格线性步骤：读取 → 比对 → 写入 → 更新日志
使用 Agno Workflow 串联 wiki_analyst → wiki_writer
"""
from agno.workflow import Workflow
from agno.agent import Agent
from typing import Optional

from agents.wiki_analyst import WikiAnalyst
from agents.wiki_writer import WikiWriter
from prompts.wiki_prompt import build_analyst_system_prompt, build_writer_system_prompt


class IngestFlow(Workflow):
    """
    摄入流水线（Ingest Flow）。

    设计原则：
    - 步骤 1：wiki_analyst 只读不做写，输出分析报告
    - 步骤 2：wiki_writer 接收报告，执行原子性磁盘操作
    - 中间不允许跳过任何步骤
    - 不允许 analyst 和 writer 并行执行（两者职责严格串行）
    """

    name: str = "wiki_ingest_flow"
    description: str = "将原始资料摄入为 Wiki 页面，严格按 Analyze → Write 顺序执行"

    # ── 参数 ───────────────────────────────────────────────────
    source_file: str              # data/raw/ 下的文件名
    context: Optional[str] = None  # 额外上下文描述

    def run(self) -> dict:
        analyst = WikiAnalyst()
        writer = WikiWriter()

        # ── Step 1: 分析 ──────────────────────────────────────
        print(f"[IngestFlow] 开始分析来源文件: {self.source_file}")
        report = analyst.ingest(source_file=self.source_file, context=self.context)
        print(f"[IngestFlow] 分析完成，生成 {len(report.get('actions', []))} 个操作")

        # ── Step 2: 写入 ──────────────────────────────────────
        print(f"[IngestFlow] 开始写入 Wiki...")
        results = writer.apply(report)
        print(f"[IngestFlow] 写入完成，{len(results)} 个操作")

        return {
            "source_file": self.source_file,
            "actions": report.get("actions", []),
            "results": results,
            "new_concepts": report.get("new_concepts", []),
            "tensions": report.get("tensions", []),
            "confidence": report.get("confidence", 0.0),
        }
