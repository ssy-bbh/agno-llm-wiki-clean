#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
# LLM Wiki Demo — systemd 服务安装器 (Linux)
# 用法: sudo bash install_service.sh [port]
# ═══════════════════════════════════════════════════════
set -e

PORT="${1:-8888}"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_NAME="llm-wiki"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/uvicorn"

if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 sudo 运行此脚本"
    echo "   sudo bash $0 $PORT"
    exit 1
fi

if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ 未找到虚拟环境，请先运行 bash deploy.sh"
    exit 1
fi

echo "▶ 安装 systemd 服务: $SERVICE_NAME"
echo "  端口: $PORT"
echo "  项目: $PROJECT_DIR"

cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=LLM-Wiki OS API Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${PROJECT_DIR}
Environment=PYTHONUNBUFFERED=1
Environment=PATH=${PROJECT_DIR}/.venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=${VENV_PYTHON} app:app --host 0.0.0.0 --port ${PORT} --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

echo ""
echo "✅ 服务已启动！"
echo ""
echo "管理命令："
echo "  systemctl status $SERVICE_NAME    # 查看状态"
echo "  systemctl restart $SERVICE_NAME   # 重启"
echo "  systemctl stop $SERVICE_NAME      # 停止"
echo "  journalctl -u $SERVICE_NAME -f    # 查看日志"
echo ""
echo "访问地址: http://$(hostname -I | awk '{print $1}'):${PORT}"
