---
name: new-feature
description: 新功能開發技能：從需求澄清到實作、驗證與交付，重視最小可行、可維護與低風險。
---

# New Feature Skill

## Goal
以小步快跑方式交付新功能，確保需求對齊、相容性、可測試性與可回滾性。

## Use This Skill When
- 使用者要求新增功能、擴充流程、加入新選項或新介面
- 需要在既有架構中插入新能力，並維持既有行為
- 需要把需求拆成可交付的最小增量

## Do Not Use This Skill When
- 問題本質是 bug（請改用 debug 技能）
- 只需重構且不改變外部行為

## Feature Workflow
1. Clarify intent
- 釐清使用者目標、成功條件、非目標（out of scope）
- 定義輸入、輸出、限制與相容性要求

2. Inspect current architecture
- 找到現有資料流、關鍵模組、可擴充點
- 確認是否已有可重用邏輯，避免重複實作

3. Design minimal increment
- 先做最小可行版本（MVP）
- 明確列出介面/設定變更與預設值策略

4. Implement safely
- 優先局部改動，不破壞既有 public API
- 對邊界條件與錯誤路徑加入必要防護

5. Validate behavior
- 驗證新功能主流程
- 驗證既有關鍵流程無回歸
- 若可行，補充測試或至少提供手動驗證步驟

6. Communicate delivery
- 說明改了什麼、為何這樣改、影響範圍與限制

## Output Template
- Requirement: 功能需求與成功條件
- Plan: 最小增量設計與涉及模組
- Changes: 主要改動（檔案/函式）
- Validation: 驗證方式與結果
- Compatibility: 對舊行為/設定的影響
- Follow-ups: 可選下一步

## Heuristics
- 先整合、後抽象：避免過早泛化
- 預設值應安全且可預期
- 新增設定時，維持向後相容與明確 fallback
- 功能切入點要可觀測（log / 狀態訊息）

## Safety Rules
- 不以大範圍重寫取代小幅可驗證改動
- 不移除既有行為，除非需求明確要求
- 涉及風險變更時，需註明回退方式
