from agents.wiki_analyst import WikiAnalyst

analyst = WikiAnalyst()
# 随便喂一段关于你项目的文本
report = analyst.analyze("VisionVoice 是一款基于端侧 AI 的实时目标识别与发音训练应用，使用了量化后的 YOLOv8 模型。")

import json
print("成功拿到 JSON！内容如下：")
print(json.dumps(report, indent=2, ensure_ascii=False))