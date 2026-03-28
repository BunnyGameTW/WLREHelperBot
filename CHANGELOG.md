# Changelog

## 0.1.6 - 2026-03-29
- README 改為精簡版，完整歷史移至 `CHANGELOG.md`。
- 新增獨立的 PC / EMU PyInstaller spec，改用 `launcher.py` 與 `launcher_emu.py` 作為打包入口。
- 補上 `pywin32` 相依與 PyInstaller hidden imports，確保 `win32gui` / `win32ui` 與 `PyQt5.sip` 可正確打包。

## 0.1.5 - 2026-03-29
- 修正 CMD 模式：`Ctrl+C` 停止後會正確關閉快捷鍵監聽並回到模式選單，可再次輸入文字。
- 修正 `start_gui.bat`：切換 UTF-8 碼頁與 Python UTF-8 輸出，避免中文亂碼。

## 0.1.4 - 2026-03-28
- 補齊 EMU 介面多國語言：新增「瀏覽」按鈕、個別裝置空狀態提示，並讓個別裝置活力策略文案可隨語言切換更新。
- 修正 CMD 模式 `Ctrl+C`：中斷後會停止並等待所有 bot 執行緒結束，不再持續輸出 debug log。

## 0.1.3 - 2026-03-28
- 修正 CMD `Ctrl+C`：在快捷鍵監聽模式可正確觸發主執行緒中斷。
- README 移除不存在的 `main_gui.py`，改為 `autoPVE.py` / `launcher_emu.py` 啟動與打包說明。
- 補齊多國語言鍵值：LDPlayer 限制與路徑說明、`device_strategy_hint`、`btn_resume`。
- 暫停後按鈕文字改為「繼續執行」（含多語）。

## 0.1.2 - 2026-03-28
- PC 設定頁加入「目前套用的設定」區塊，同 EMU 設定介面。
- CMD 模式簡化：移除「3. 自動選擇」，模式選擇與執行合一。
- CMD 控制指令改為 Ctrl+D / Ctrl+P / Ctrl+C，使用 `msvcrt.getch()` 即時回應。
- CMD 標頭加入版本號顯示。

## 0.1.1 - 2026-03-28
- 修正 PC 啟動頁提示字串，移除「1. [PC 模式]」顯示。
- 修正 GUI 除錯模式：啟動後會正確套用，控制台可顯示偵測分數（含 HIT/MISS）。
- 修正 GUI 暫停/停止狀態競合：停止時會重置全域暫停狀態。
- 更新 PC/EMU 說明頁：顯示目前版本號、加入使用限制（不可開省電模式、遊戲語言需繁中）。
- 修正說明頁 `help_steps_desc` 的 `<br>` 換行顯示。

## 0.1.0 - 2026-03-28
- 新增 Copilot skills：`debug`、`new-feature`。
- 建立版本檔 `VERSION`。
- 將核心邏輯拆分至 `core/` 套件，保留 `autoPVE.py` 作為主入口與相容層。