#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
# LLM Wiki Demo — 一键部署脚本 (Linux / macOS)
# 用法: bash deploy.sh [port]
#   port 默认 8888
# ═══════════════════════════════════════════════════════
set -e

PORT="${1:-8888}"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
NODE_REQUIRED="18"

echo "═══════════════════════════════════════════════"
echo "  LLM Wiki Demo — 一键部署"
echo "  项目目录: $PROJECT_DIR"
echo "  端口: $PORT"
echo "═══════════════════════════════════════════════"

# ── 1. 检查 Python ──
echo ""
echo "▶ [1/6] 检查 Python 环境..."
PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$minor" -ge 11 ]; then
            PYTHON="$cmd"
            echo "  ✅ Python $ver ($cmd)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "  ❌ 需要 Python 3.11+，请先安装："
    echo "     Ubuntu/Debian: sudo apt install python3.11 python3.11-venv"
    echo "     macOS: brew install python@3.11"
    echo "     CentOS/RHEL: sudo dnf install python3.11"
    exit 1
fi

# ── 2. 创建虚拟环境 ──
echo ""
echo "▶ [2/6] 创建 Python 虚拟环境..."
if [ ! -d "$VENV_DIR" ]; then
    $PYTHON -m venv "$VENV_DIR"
    echo "  ✅ 已创建 $VENV_DIR"
else
    echo "  ⏭️  已存在，跳过"
fi
source "$VENV_DIR/bin/activate"

# ── 3. 安装 Python 依赖 ──
echo ""
echo "▶ [3/6] 安装 Python 依赖..."
pip install --upgrade pip -q
pip install -r "$PROJECT_DIR/requirements.txt" -q
echo "  ✅ $(pip list --format=freeze 2>/dev/null | wc -l) 个包已安装"

# ── 4. 检查 Node.js（前端构建）──
echo ""
echo "▶ [4/6] 检查 Node.js + 构建前端..."
WEB_DIR="$PROJECT_DIR/web"
if [ -d "$WEB_DIR/dist" ] && [ -f "$WEB_DIR/dist/index.html" ]; then
    echo "  ⏭️  前端已构建，跳过（如需重新构建请删除 web/dist/）"
else
    if command -v node &>/dev/null; then
        node_ver=$(node -v | sed 's/v//' | cut -d. -f1)
        if [ "$node_ver" -ge "$NODE_REQUIRED" ]; then
            echo "  Node.js $(node -v)"
            cd "$WEB_DIR"
            npm install --silent 2>/dev/null
            npm run build
            echo "  ✅ 前端构建完成"
            cd "$PROJECT_DIR"
        else
            echo "  ⚠️  Node.js 版本过低 ($(node -v))，需要 v${NODE_REQUIRED}+"
            echo "     请手动构建前端: cd web && npm install && npm run build"
        fi
    else
        echo "  ⚠️  未检测到 Node.js，跳过前端构建"
        echo "     请安装 Node.js v${NODE_REQUIRED}+: https://nodejs.org"
        echo "     然后: cd web && npm install && npm run build"
    fi
fi

# ── 5. 配置 .env ──
echo ""
echo "▶ [5/6] 检查 .env 配置..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "  ✅ 已从模板创建 .env，请编辑填入你的 API Key："
    echo "     nano $PROJECT_DIR/.env"
    echo ""
    echo "  ⚠️  至少需要配置 QWEN_API_KEY 才能使用 LLM 功能"
else
    echo "  ⏭️  .env 已存在，跳过"
fi

# ── 6. 创建数据目录 ──
echo ""
echo "▶ [6/6] 初始化数据目录..."
mkdir -p "$PROJECT_DIR/data/raw"
mkdir -p "$PROJECT_DIR/data/wiki"
mkdir -p "$PROJECT_DIR/data/.ingest_status"
mkdir -p "$PROJECT_DIR/storage/sqlite"
mkdir -p "$PROJECT_DIR/storage/lancedb"
echo "  ✅ 数据目录已就绪"

# ── 完成 ──
echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ 部署完成！"
echo ""
echo "  启动方式（二选一）："
echo ""
echo "  🚀 前台运行（调试用）："
echo "     cd $PROJECT_DIR"
echo "     source .venv/bin/activate"
echo "     uvicorn app:app --host 0.0.0.0 --port $PORT"
echo ""
echo "  🔧 systemd 服务（生产用）："
echo "     sudo bash $PROJECT_DIR/install_service.sh $PORT"
echo ""
echo "  访问地址: http://localhost:$PORT"
echo "═══════════════════════════════════════════════"
