"""
main.py — Agno-LLM-Wiki 终极中央控制台 (完美模拟物理执行版)
"""
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
WORKFLOWS_DIR = PROJECT_ROOT / "workflows"

def run_script(script_name: str):
    """完美模拟人类行为：先 cd 到 workflows，再执行脚本"""
    script_file = WORKFLOWS_DIR / script_name
    if not script_file.exists():
        print(f"❌ 找不到文件: {script_file}")
        return

    try:
        # 💡 核心修复：把 cwd 设置为 WORKFLOWS_DIR！
        # 这样你代码里的 "../data/wiki" 就能完美指回真正的目录，绝不报错！
        subprocess.run([sys.executable, script_name], cwd=WORKFLOWS_DIR)
    except Exception as e:
        print(f"❌ 执行中断: {e}")

def main():
    while True:
        print("\n" + "=".join([""] * 65))
        print("🚀 [Agno-LLM-Wiki] 智能知识图谱引擎控制台")
        print("=".join([""] * 65))
        print("  [1] 🧠 知识摄入 (Ingest)   - 读取生肉文档，大模型抽取标准概念")
        print("  [2] 🕳️  黑洞探测 (AutoFill) - 扫描图谱死链，大模型自动补全真空节点")
        print("  [3] 🕷️  全局织网 (Lint)      - 单沙箱局部扫描，生成反向链接与审查死链")
        print("-".join([""] * 65))

        choice = input("👉 请输入流水线序号 (输入 q 退出): ").strip()

        if choice.lower() == 'q':
            print("👋 引擎已安全关闭。")
            sys.exit(0)

        elif choice == '1':
            run_script("ingest_flow.py")

        elif choice == '2':
            run_script("autofill_flow.py")

        elif choice == '3':
            run_script("lint_flow.py")

        else:
            print("⚠️ 无效的序号，请重新输入！")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 引擎已强制中止。")
        sys.exit(0)