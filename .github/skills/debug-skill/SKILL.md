---
name: debug-skill
description: 系統化除錯技能：重現問題、縮小範圍、找根因、提出最小修正、驗證不回歸。
---

# Debug Skill

## Goal
以可重現、可驗證、最小風險的方式處理錯誤與異常行為。

## Use This Skill When
- 使用者要求「debug / 修 bug / 找錯誤原因 / 為什麼壞掉」
- 測試失敗、執行例外、效能異常、行為回歸
- 需要從 log、stack trace、設定差異中找根因

## Do Not Use This Skill When
- 僅需新增純功能且沒有故障情境
- 只是做介面文案微調或格式整理

## Debug Workflow
1. Clarify failure
- 釐清「預期行為 vs 實際行為」
- 擷取錯誤訊息、堆疊、重現步驟、影響範圍

2. Reproduce reliably
- 先讓問題可穩定重現，再開始修
- 若無法重現，先補觀測點（log / asserts / guards）

3. Narrow scope
- 用二分法定位：輸入、狀態、邊界、相依元件
- 檢查最近變更與設定差異

4. Find root cause
- 描述直接原因與根本原因
- 確認不是只修表象（symptom fix）

5. Apply minimal safe fix
- 優先小改動，避免不必要重構
- 保持現有 public API 與專案風格

6. Verify and guard
- 重跑失敗案例、相關測試與基本 smoke test
- 補上回歸測試或防呆判斷

7. Report clearly
- 說明根因、修正點、驗證結果、剩餘風險

## Output Template
- Problem: 一句話描述故障
- Reproduction: 可重現步驟與環境
- Root cause: 根因與觸發條件
- Fix: 具體改動（檔案/函式）
- Validation: 測試或手動驗證結果
- Residual risk: 仍待觀察項目

## Heuristics
- 優先檢查：空值、索引邊界、競態、時序、平台差異、編碼/時區、設定檔
- 觀察資料流而非猜測：輸入 -> 轉換 -> 狀態 -> 輸出
- 對外部 I/O（檔案/網路/裝置）先加 timeout、重試與錯誤訊息

## Safety Rules
- 不做破壞性命令（如重置未備份資料）
- 不暴露敏感資訊（token、密碼、私鑰）
- 若修正可能改變行為，需明確標註影響範圍
