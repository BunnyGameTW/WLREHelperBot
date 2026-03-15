# WLREPVEBot

這是一個用於自動化 PVE 操作的 Windows 專案，提供 GUI 與 CLI 兩種模式。  
GUI 介面支援多裝置與個別活力策略，並提供多語系切換。

## 功能重點
- GUI 模式（建議）：選擇模式、裝置、設定參數並啟動/暫停/停止
- CLI 模式：以命令列互動控制（可選）
- PC 視窗模式 / 模擬器模式
- 可自訂等待時間、辨識閾值、活力策略
- 多語系介面（`localization.json`）
- 模擬器名稱顯示：優先使用雷電自訂名稱，找不到則回退裝置型號

## 環境需求
- Windows 10/11
- Python 3.7+
- 依賴套件（見 `requirements.txt`）

## 快速開始（GUI）
1. 雙擊 `start_gui.bat`
2. 選擇模式與裝置
3. 調整設定後按「啟動」

## 設定檔
- `default_config.json`：系統預設值
- `bot_config.json`：你儲存的設定（建議保留在本機，不要提交）
- `localization.json`：多語系文字

## 資料夾說明
- `templates/`：影像辨識模板
- `debug/`：除錯用測試腳本與截圖
- `output/`：打包後的執行檔輸出位置（已加入 .gitignore）

## 打包成可執行檔（無 Python）
本專案可使用 PyInstaller 產出單一執行檔：

```bash
python -m pip install pyinstaller
pyinstaller --noconsole --onefile ^
  --name WLREPVEBot ^
  --icon app.ico ^
  --exclude-module pyaudio ^
  --add-data "app.ico;." ^
  --add-data "templates;templates" ^
  --add-data "localization.json;." ^
  --add-data "default_config.json;." ^
  --add-data "bot_config.json;." ^
  --add-binary "adb.exe;." ^
  --add-binary "AdbWinApi.dll;." ^
  --add-binary "AdbWinUsbApi.dll;." ^
  --distpath output ^
  main_gui.py
```

輸出位置：`output/WLREPVEBot.exe`

## 備註
- 若防毒誤判，可將輸出檔加入信任清單。
- 模擬器名稱顯示若無法取得自訂名稱，會回退顯示裝置型號。
