import subprocess
import sys


def run():
    # sys.executable 保证调用的是你当前正在使用的、装了所有依赖的 Python
    print("🚀 Step 1: Ingesting...")
    try:
        subprocess.run([sys.executable, "-m", "workflows.ingest_flow"], check=True)

        print("\n🧹 Step 2: Linting...")
        subprocess.run([sys.executable, "-m", "workflows.lint_flow"], check=True)

        print("\n✅ 集成测试跑通了！")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 流程中断：脚本返回了错误码 {e.returncode}，请检查上方业务日志。")


if __name__ == "__main__":
    run()