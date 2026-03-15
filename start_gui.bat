@echo off
REM === 女王化身為無情的戰爭機器 小助手 - 啟動腳本 ===
REM 檢查Python環境
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python not found. Please install Python 3.7+
    pause
    exit /b 1
)

REM 檢查並安裝依賴
echo 📦 Checking dependencies...
pip install -r requirements.txt -q

if errorlevel 1 (
    echo ❌ Failed to install dependencies
    pause
    exit /b 1
)

echo ✅ Dependencies OK

REM 以管理員權限運行GUI（用于鼠標檢測）
echo 🚀 Starting GUI...
python main_gui.py

if errorlevel 1 (
    echo ❌ GUI failed to start
    pause
    exit /b 1
)

pause
