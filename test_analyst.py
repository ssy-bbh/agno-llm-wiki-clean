from agents.wiki_analyst import WikiAnalyst
from agents.wiki_writer import WikiWriter

# 1. 初始化两员大将
analyst = WikiAnalyst()
writer = WikiWriter()

dummy_text = "VisionVoice 是一款基于端侧 AI 的实时目标识别与发音训练应用，使用了量化后的 YOLOv8 模型。"

# 2. 执行第一步：分析并吐出 JSON
print("=== Step 1: 分析并提取知识 ===")
report = analyst.analyze(dummy_text)

# 3. 执行第二步：写盘
print("\n=== Step 2: 根据报告写入磁盘 ===")
writer.execute(report)

print("\n🎉 摄入流水线测试完成！去看看 data/wiki/concepts/ 目录下是不是多了一个文件！")