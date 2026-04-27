from agents.wiki_analyst import WikiAnalyst
from agents.wiki_writer import WikiWriter

analyst = WikiAnalyst()
writer = WikiWriter()

# 给一段包含多个技术栈的文本
dummy_text = """
VisionVoice 的发音评估模块没有使用传统的云端 API，而是本地部署了 Wav2Vec2 这个自监督语音模型。
这使得它能与 YOLOv8 视觉模型在本地协同工作，实现零延迟的交互。
"""

print("=== Step 1: 分析并生成带双链的动作 ===")
report = analyst.analyze(dummy_text)

# 打印出来看看双链有没有加上
import json
print(json.dumps(report, indent=2, ensure_ascii=False))

print("\n=== Step 2: 写入磁盘 ===")
writer.execute(report)

print("\n🎉 写入完成！去检查生成的文件里是否有 [[Wav2Vec2]] 和 [[YOLOv8]] 这样的双链吧！")