@echo off
chcp 65001 >nul
color 0A
title LLM-Wiki AgentOS 中枢控制台

echo ========================================================
echo   🚀 正在启动 LLM-Wiki 专属 AI 中台...
echo ========================================================
echo.

:: --- 🚀 新增：自动清理 7777 端口的僵尸进程 ---
:: --- 🚀 新增：精准清理 7777 端口的僵尸进程 ---
echo [INFO] 检查端口 8000 是否被占用...
FOR /F "tokens=5" %%T IN ('netstat -a -n -o ^| findstr ":8000"') DO (
    echo [WARN] 发现僵尸进程 PID: %%T，正在强行清理...
    taskkill /f /pid %%T >nul 2>&1
)

:: --------------------------------------------
:: --------------------------------------------

if exist ".venv\Scripts\activate.bat" (
    echo [INFO] 正在激活虚拟环境...
    call .venv\Scripts\activate.bat
)

if not exist ".env" (
    echo [ERROR] 缺少 .env 文件，请先配置 API Keys!
    pause
    exit /b
)

echo.
echo [INFO] 启动 AgentOS 服务...
echo [INFO] 请在服务启动后，前往浏览器访问: https://app.agno.com/
echo [INFO] 确保 Endpoint 选为: localhost:8000
echo.
echo ========================================================

python app.py

pause