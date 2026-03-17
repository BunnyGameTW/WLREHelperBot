# WLREPVEBot

這是一個用於自動化 PVE 操作的 Windows 專案，提供 GUI 與 CLI 兩種模式。  
GUI 介面支援多裝置與個別活力策略，並提供多語系切換。

## 功能重點
- GUI 模式（建議）：選擇模式、裝置、設定參數並啟動/暫停/停止
- CLI 模式：以命令列互動控制（支持 PC / 模擬器模式直接執行自動對戰）
- PC 視窗模式 / 模擬器模式
- 可自訂等待時間、辨識閾值、活力策略
- 多語系介面（`localization.json`）
- 模擬器名稱顯示：優先使用雷電自訂名稱，找不到則回退裝置型號

## 架構設計

### 核心邏輯與 UI 分離

```
autoPVE.py          ← 核心邏輯模組（DriftBot、模板匹配、截圖、點擊、配置）
├── launcher.py     ← PC 模式 GUI（整合 autoPVE 核心邏輯）
├── launcher_emu.py ← EMU 模式 GUI（整合 autoPVE 核心邏輯）
├── launcher_cmd.py ← CMD 命令行模式（直接呼叫 autoPVE 核心邏輯）
└── main_gui.py     ← 統一 GUI（PC + EMU 雙模式，完整功能）
```

### 自動對戰邏輯流程

```
迴圈:
  檢查暫停 → 截圖 → 辨識狀態
  ├── 戰鬥中 → 等待戰鬥結束
  ├── 等待開戰 → 30 秒超時檢查
  └── 準備畫面:
       ├── 偵測低活力 → 停止 or 自動補充
       ├── 搜尋對手按鈕 → 點擊 → 確認 → 等待開戰
       └── 持續掃描
```

### 跨平台設計（PC + EMU 同套邏輯）

| 功能 | PC 模式 | EMU 模式 |
|------|---------|----------|
| 截圖 | win32gui PrintWindow | ADB screencap |
| 點擊 | pydirectinput | ADB input tap |
| 設備偵測 | EnumWindows | ADB connect |
| 模板匹配 | 共用 cv2.matchTemplate | 共用 cv2.matchTemplate |
| 配置結構 | 共用 bot_config.json | 共用 bot_config.json |

## 啟動方式

### 方式一：啟動選單（推薦）
```bash
# 雙擊 start_gui.bat
# 選擇 1=PC模式 / 2=EMU模式 / 3=CMD模式
```

### 方式二：直接啟動指定模式
```bash
python launcher.py       # PC 模式 GUI
python launcher_emu.py   # EMU 模式 GUI
python launcher_cmd.py   # CMD 命令行模式
python main_gui.py       # 統一 GUI（PC + EMU 雙模式）
```

## 環境需求
- Windows 10/11
- Python 3.7+
- 依賴套件（見 `requirements.txt`）

## 設定檔
- `default_config.json`：系統預設值
- `bot_config.json`：你儲存的設定（建議保留在本機，不要提交）
- `localization.json`：多語系文字

## 資料夾說明
- `templates/`：影像辨識模板
- `debug/`：除錯用測試腳本與截圖
- `output/`：打包後的執行檔輸出位置（已加入 .gitignore）
- `core/`：核心工具模組
- `emulator/`：模擬器管理模組
- `pc/`：PC 視窗管理模組

## 開發進度

| 項目 | 狀態 | 說明 |
|------|------|------|
| 核心自動對戰邏輯 | ✅ 完成 | autoPVE.py - DriftBot 類別 |
| PC 模式 GUI | ✅ 完成 | launcher.py - 整合核心邏輯 |
| EMU 模式 GUI | ✅ 完成 | launcher_emu.py - 整合核心邏輯 |
| CMD 命令行模式 | ✅ 完成 | launcher_cmd.py - PC/EMU 雙模式 |
| 統一 GUI | ✅ 完成 | main_gui.py - 完整功能 |
| 多語系支援 | ✅ 完成 | i18n.py + localization.json |
| 配置系統 | ✅ 完成 | 等待時間 / 閾值 / 活力策略 |
| 模擬器偵測 | ✅ 完成 | ADB + 雷電/BlueStacks/MuMu/Nox |
| UI/邏輯分離 | ✅ 完成 | 核心邏輯在 autoPVE.py，UI 為獨立檔案 |
| 偵測斷線自動重連 | 🔲 規劃中 | 預留接口 |

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
