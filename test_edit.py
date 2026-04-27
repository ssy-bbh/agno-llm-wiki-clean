from agents.wiki_analyst import WikiAnalyst
from agents.wiki_writer import WikiWriter

analyst = WikiAnalyst()
writer = WikiWriter()

# 我们模拟分析师同时看到了“现有 Wiki 的残缺内容”和“新资料”
dummy_text = """
【目标文件内容】: concepts/yolov8.md 目前包含以下段落：
## Details
（等待后续扩展）

【今天新摄入的资料】:
在 VisionVoice 项目中，YOLOv8 模型被成功部署于 iPad Pro 上。得益于端侧 AI 算力，相比云端方案，其推理延迟降低了 40%。
"""

print("=== Step 1: 让大模型分析新资料，生成 edit 动作 ===")
report = analyst.analyze(dummy_text)
print("\n【Debug】大模型生成的完整报告是：")
import json
print(json.dumps(report, indent=2, ensure_ascii=False))
print("\n=== Step 2: 包工头拿着 edit 动作执行精细手术 ===")
writer.execute(report)

print("\n🎉 测试结束，去看看 concepts/yolov8.md 里的内容变了没有！")