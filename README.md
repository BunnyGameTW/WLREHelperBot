# WLREPVEBot

這是一個用於自動化 PVE 操作的 Windows 專案，提供 PC GUI、EMU GUI 與 CMD 三種啟動方式。

## 版本資訊
- 目前版本：`0.1.6`

## 功能重點
- PC 模式 GUI：控制本地遊戲視窗
- EMU 模式 GUI：僅支援 LDPlayer，支援多開與個別設備策略
- CMD 模式：支援 Ctrl+D / Ctrl+P / Ctrl+C 快捷鍵控制
- 多語系介面：繁中 / 簡中 / English
- 設定分離：PC 使用 `bot_config_pc.json`，EMU 使用 `bot_config_emu.json`

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
