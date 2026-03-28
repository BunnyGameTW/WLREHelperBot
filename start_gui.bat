@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM === 女王化身為無情的戰爭機器 小助手 - 啟動菜單 ===
REM 檢查Python環境
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.7+
    pause
    exit /b 1
)

REM 檢查並安裝依賴
echo [INFO] Checking dependencies...
python -m pip install -r requirements.txt -q

if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo [OK] Dependencies OK

REM === 顯示選擇菜單 ===
:menu
cls
echo.
echo ====================================
echo  女王化身為無情的戰爭機器 小助手
echo ====================================
echo.
echo [1] PC 模式 (單本地窗口, 實時控制)
echo [2] EMU 模式 (多模擬器, 後台運行)
echo [3] CMD 模式 (命令行版本)
echo [Q] 退出
echo.

set /p choice="請選擇 [1/2/3/Q]: "

if /i "%choice%"=="1" (
    echo [INFO] 啟動 PC 模式...
    python launcher.py
) else if /i "%choice%"=="2" (
    echo [INFO] 啟動 EMU 模式...
    python launcher_emu.py
) else if /i "%choice%"=="3" (
    echo [INFO] 啟動 CMD 模式...
    python launcher_cmd.py
) else if /i "%choice%"=="Q" (
    echo [INFO] 退出
    exit /b 0
) else (
    echo [ERROR] 選擇無效，請重新選擇
    timeout /t 2 >nul
    goto menu
)

if errorlevel 1 (
    echo [ERROR] 啟動失敗
    pause
    exit /b 1
)

echo.
echo [INFO] 程式已關閉
timeout /t 2 >nul
goto menu
