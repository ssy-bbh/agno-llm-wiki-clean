from agents.wiki_analyst import WikiAnalyst
from agents.wiki_writer import WikiWriter
import json

analyst = WikiAnalyst()

# 这一次，分析师会去真正读取你刚才创建的 data/wiki/index.md
dummy_raw_text = """
我们在项目中不仅使用了 YOLOv8 进行目标检测，还引入了 Transformer 架构来处理时序数据。
"""

print("=== 正在测试真实的上下文感知能力 ===")
report = analyst.analyze(dummy_raw_text)

print("\n【分析师的决策结果】：")
print(json.dumps(report, indent=2, ensure_ascii=False))
print("\n=== 正在由包工头执行物理写盘 ===")
writer = WikiWriter()
writer.execute(report)

print("\n🎉 闭环测试结束！请去检查：")
print("1. concepts/transformer.md 是否被成功创建？")
print("2. index.md 里是否在 YOLOv8 后面成功插队了 [[Transformer]]？")