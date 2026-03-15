# 女王化身為無情的戰爭機器 小助手
## 完整功能實現指南

### ✅ 已實現功能

#### 1️⃣ **多語言系統** (需求1)
- ✅ 建立 `localization.json` 配置文件
- ✅ 支持繁體中文 (zh_TW)、簡體中文 (zh_CN)、英文 (en)
- ✅ autoPVE.py 中集成 `STRINGS` 全局字符串系統
- ✅ GUI中可動態切換語言

**使用方法**：
```python
# 修改LANGUAGE變量以切換語言
LANGUAGE = "zh_TW"  # 改為 "zh_CN" 或 "en"
```

#### 2️⃣ **GUI界面** (需求4)
- ✅ 建立 PyQt5 完整GUI程式 (`main_gui.py`)
- ✅ 三個標籤頁：啟動、配置、控制台
- ✅ 多語言支持與實時切換
- ✅ 完整替代CMD界面

**啟動方法**：
```bash
python main_gui.py
# 或使用批處理
start_gui.bat
```

#### 3️⃣ **快捷鍵系統** (需求2)
- ✅ Ctrl+D - 切換除錯模式
- ✅ Ctrl+P - 暫停/繼續偵測
- ✅ Ctrl+C - 停止腳本
- ✅ GUI和CMD皆支持

#### 4️⃣ **PC模式鼠標保護** (需求3)
- ✅ 實時監測鼠標移動
- ✅ 檢測到移動立即暫停並提示用戶
- ✅ 防止誤操作導致程序錯誤

**工作機制**：
```
運行中偵測到鼠標移動 → 腳本暫停 → 提示用戶
用戶停止操作 → 按 Ctrl+P 繼續
```

---

### 🔧 安裝與使用

#### 步驟1：安裝依賴
```bash
pip install -r requirements.txt
```

或在Windows上直接執行：
```bash
start_gui.bat
```

#### 步驟2：啟動程式
**GUI模式（推薦）**：
```bash
python main_gui.py
# 或
start_gui.bat
```

**CMD模式（傳統）**：
```bash
python autoPVE.py
```

---

### 📋 功能說明

#### 語言切換
在GUI界面右上角選擇語言：
- 繁體中文 (Traditional Chinese)
- 簡體中文 (Simplified Chinese)
- English

#### 快捷鍵操作

| 快捷鍵 | 功能 | 說明 |
|-------|------|------|
| Ctrl+D | 除錯模式 | 開啟/關閉詳細日誌 |
| Ctrl+P | 暫停/繼續 | 臨時暫停或恢復偵測 |
| Ctrl+C | 停止腳本 | 完全停止所有進程 |

#### 配置文件
配置自動保存於 `bot_config.json`：
```json
{
  "wait_times": {
    "scan_interval": 1.0,
    "wait_battle_check": 30.0,
    ...
  },
  "energy_strategy": false,
  "thresholds": {...},
  "device_configs": {...}
}
```

#### 多語言字符串配置
所有文本字符串存儲在 `localization.json`，結構：
```json
{
  "zh_TW": {
    "app_title": "女王化身為無情的戰爭機器 小助手",
    "bot_start": "🚀 開始循環...",
    ...
  },
  "zh_CN": {...},
  "en": {...}
}
```

---

### 🛡️ PC模式鼠標保護細節

**保護機制**：
1. 每幀檢測鼠標位置
2. 移動超過5像素則視為操作
3. 自動暫停腳本並顯示警告
4. 用戶停止操作後可按 Ctrl+P 繼續

**範例日誌**：
```
[PC-Main] ⚠️  偵測到滑鼠移動！PC模式運行中請勿操作滑鼠。
[PC-Main] 為了安全起見，腳本已暫停。請停止滑鼠操作後按 Ctrl+P 繼續。
[PC-Main] ⏸️  已暫停
[用戶按 Ctrl+P]
[PC-Main] ▶️  已繼續
```

---

### 📊 GUI界面功能

#### 啟動標籤 (Launch Tab)
- 選擇運行模式（PC/模擬器）
- 選擇目標設備
- 一鍵啟動/停止
- 實時進度顯示

#### 配置標籤 (Config Tab)
- 調整等待時間
- 修改分數門檻
- 設置能量策略
- 配置保存

#### 控制台標籤 (Console Tab)
- 實時日誌輸出
- 快捷鍵幫助
- 清空日誌功能
- 彩色消息顯示

---

### ⚙️ 自訂語言新增

在 `localization.json` 中新增語言（例如日文）：
```json
{
  "ja": {
    "app_title": "女王は無情の戦争マシンアシスタント",
    "bot_start": "🚀 ループ開始...",
    ...
  }
}
```

然後在程式中使用：
```python
LANGUAGE = "ja"  # GUI中添加語言選項
```

---

### 🐛 故障排解

**問題1：GUI無法啟動**
```bash
# 檢查PyQt5是否正確安裝
pip install PyQt5==5.15.7 --upgrade
```

**問題2：快捷鍵無效**
```bash
# 安裝keyboard模塊
pip install keyboard==0.13.5

# Windows需要管理員權限
# 以管理員身份運行批處理文件
```

**問題3：語言配置無法加載**
```bash
# 確保localization.json在執行目錄
# 檢查JSON文件格式是否正確
python -m json.tool localization.json
```

---

### 📁 檔案結構
```
IWillBeatPenguinPython/
├── autoPVE.py                 # 核心邏輯引擎
├── main_gui.py               # PyQt5 GUI主程式
├── localization.json         # 多語言配置
├── bot_config.json          # 運行時配置
├── requirements.txt         # 依賴列表
├── start_gui.bat            # Windows啟動腳本
└── templates/               # 模板圖片文件夾
    ├── ref_main_title.png
    ├── btn_add.png
    ├── btn_confirm.png
    ├── btn_join.png
    ├── ref_in_battle.png
    ├── ref_energy_low.png
    └── ref_energy_9.png
```

---

### 🚀 未來擴展

- [ ] 集成PySimpleGUI作為簡化替代方案
- [ ] 添加Web界面（Flask/Django）
- [ ] 實現遠程控制功能
- [ ] 音聲提示和通知系統
- [ ] 詳細的統計與分析面板
- [ ] 配置文件加密與備份

---

### 📞 使用建議

1. **首次運行**：使用GUI進行配置，更直觀
2. **自動化**：使用 `start_gui.bat` 一鍵啟動
3. **多語言**：根據偏好選擇語言
4. **性能調優**：在配置標籤調整等待時間
5. **安全運行**：PC模式時勿碰滑鼠，避免觸發保護機制

---

### ✨ 已實現的所有需求總結

| # | 需求 | 狀態 | 實現方式 |
|----|------|------|---------|
| 1 | 多語言字符串配置 | ✅ | localization.json + STRINGS |
| 2 | Ctrl+D/P 快捷鍵 | ✅ | keyboard 模塊 + GUI熱鍵 |
| 3 | PC鼠標保護 | ✅ | win32api 鼠標檢測 + 自動暫停 |
| 4 | GUI 完全替代CMD | ✅ | PyQt5 完整GUI界面 |

---

**最後更新**: 2026年3月15日
**版本**: 2.5.0 (GUI Complete Release)
