# WLREPVEBot

這是一個用於自動化 PVE 操作的 Windows 專案，提供 PC GUI、EMU GUI 與 CMD 三種啟動方式。

## 版本資訊
- 目前版本：`0.2.0`

## 功能重點
- PC GUI、EMU GUI、CMD 三種模式分離運作，PC/EMU 各自保存設定與啟動參數。
- 自動玩家對戰、斷線重連、自動開啟功能三大流程已獨立分頁，調整與維護更直接。
- 支援分頁儲存、重置變更、恢復預設與未儲存設定防呆，避免執行時用到錯誤配置。
- 補強登入後彈窗、低活力補充、遊戲開啟檢查、視窗位置記憶與 Debug 日誌效能。
- 更新模板、多語系、圖示與打包配置；EMU 預設 `活力值9時畫面` 為 `0.95`。

## 啟動方式

### 啟動選單
```bat
start_gui.bat
```

### 直接啟動
```bat
python launcher.py
python launcher_emu.py
python launcher_cmd.py
python autoPVE.py
```

## 環境需求
- Windows 10/11
- Python 3.10+
- 相依套件見 `requirements.txt`

## 打包

### PC 版本
```bat
pyinstaller --clean --noconfirm --distpath output --workpath build/pc_build WLREPVEBot_PC.spec
```

輸出：`output/WLREPVEBot_PC.exe`

### EMU 版本
```bat
pyinstaller --clean --noconfirm --distpath output --workpath build/emu_build WLREPVEBot_EMU.spec
```

輸出：`output/WLREPVEBot_EMU.exe`

## 設定檔
- `default_config_pc.json`：PC 預設設定
- `default_config_emu.json`：EMU 預設設定
- `bot_config_pc.json`：PC 使用者設定
- `bot_config_emu.json`：EMU 使用者設定
- `localization.json`：多語系文字

## 文件
- 完整變更歷史：`CHANGELOG.md`

## 備註
- 若防毒誤判，可將輸出檔加入信任清單。
- LDPlayer 若安裝於非預設位置，請在 EMU 設定頁指定安裝路徑。
