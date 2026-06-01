@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

REM ═══════════════════════════════════════════════════════
REM LLM Wiki Demo — 一键部署脚本 (Windows)
REM 用法: deploy.bat [port]
REM   port 默认 8888
REM ═══════════════════════════════════════════════════════

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8888"
set "PROJECT_DIR=%~dp0"
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "VENV_DIR=%PROJECT_DIR%\.venv"

echo ═══════════════════════════════════════════════
echo   LLM Wiki Demo — Windows 一键部署
echo   项目目录: %PROJECT_DIR%
echo   端口: %PORT%
echo ═══════════════════════════════════════════════

REM ── 1. 检查 Python ──
echo.
echo ▶ [1/6] 检查 Python 环境...
where python >nul 2>&1
if errorlevel 1 (
    echo   ❌ 未找到 Python，请先安装 Python 3.11+
    echo      下载: https://www.python.org/downloads/
    echo      安装时务必勾选 "Add Python to PATH"
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
echo   ✅ Python %PYVER%

REM ── 2. 创建虚拟环境 ──
echo.
echo ▶ [2/6] 创建 Python 虚拟环境...
if not exist "%VENV_DIR%\Scripts\python.exe" (
    python -m venv "%VENV_DIR%"
    echo   ✅ 已创建 %VENV_DIR%
) else (
    echo   ⏭  已存在，跳过
)

REM ── 3. 安装依赖 ──
echo.
echo ▶ [3/6] 安装 Python 依赖...
call "%VENV_DIR%\Scripts\activate.bat"
pip install --upgrade pip -q
pip install -r "%PROJECT_DIR%\requirements.txt" -q
echo   ✅ 依赖安装完成

REM ── 4. 前端构建 ──
echo.
echo ▶ [4/6] 检查前端构建...
if exist "%PROJECT_DIR%\web\dist\index.html" (
    echo   ⏭  前端已构建，跳过
) else (
    where node >nul 2>&1
    if errorlevel 1 (
        echo   ⚠  未检测到 Node.js，跳过前端构建
        echo      请安装 Node.js: https://nodejs.org
        echo      然后: cd web ^&^& npm install ^&^& npm run build
    ) else (
        echo   构建前端...
        cd "%PROJECT_DIR%\web"
        call npm install
        if errorlevel 1 (
            echo   ❌ npm install 失败，请检查上方错误信息
            pause
            exit /b 1
        )
        call npm run build
        if errorlevel 1 (
            echo   ❌ npm run build 失败
            pause
            exit /b 1
        )
        cd "%PROJECT_DIR%"
        echo   ✅ 前端构建完成
    )
)

REM ── 5. 配置 .env ──
echo.
echo ▶ [5/6] 检查 .env 配置...
if not exist "%PROJECT_DIR%\.env" (
    copy "%PROJECT_DIR%\.env.example" "%PROJECT_DIR%\.env" >nul
    echo   ✅ 已从模板创建 .env
    echo   ⚠  请编辑 .env 填入你的 API Key
    echo      文件位置: %PROJECT_DIR%\.env
) else (
    echo   ⏭  .env 已存在，跳过
)

REM ── 6. 创建数据目录 ──
echo.
echo ▶ [6/6] 初始化数据目录...
if not exist "%PROJECT_DIR%\data\raw" mkdir "%PROJECT_DIR%\data\raw"
if not exist "%PROJECT_DIR%\data\wiki" mkdir "%PROJECT_DIR%\data\wiki"
if not exist "%PROJECT_DIR%\data\.ingest_status" mkdir "%PROJECT_DIR%\data\.ingest_status"
if not exist "%PROJECT_DIR%\storage\sqlite" mkdir "%PROJECT_DIR%\storage\sqlite"
if not exist "%PROJECT_DIR%\storage\lancedb" mkdir "%PROJECT_DIR%\storage\lancedb"
echo   ✅ 数据目录已就绪

REM ── 完成 ──
echo.
echo ═══════════════════════════════════════════════
echo   ✅ 部署完成！
echo.
echo   启动命令:
echo     start.bat
echo.
echo   或手动启动:
echo     cd %PROJECT_DIR%
echo     .venv\Scripts\activate
echo     uvicorn app:app --host 0.0.0.0 --port %PORT%
echo.
echo   访问地址: http://localhost:%PORT%
echo ═══════════════════════════════════════════════
pause
