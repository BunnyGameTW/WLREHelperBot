"""
純常數與工具函式
"""
import sys
import os

# 【核心設定】基準解析度
BASE_W, BASE_H = 1275, 755

# 視窗標題
WINDOW_TITLE = "飄流幻境Re:星之方舟"

# 預設比對門檻
THRESHOLD = 0.80

# 模板檔案對應
TEMPLATES_PATHS = {
    "title": "ref_main_title.png",
    "btn_add": "btn_add.png",
    "btn_confirm": "btn_confirm.png",
    "btn_join": "btn_join.png",
    "in_battle": "ref_in_battle.png",
    "energy_low": "ref_energy_low.png",
    "energy_9": "ref_energy_9.png",
}

# 平台專用配置檔名
CONFIG_FILE_PC = "bot_config_pc.json"
CONFIG_FILE_EMU = "bot_config_emu.json"


def resource_path(relative_path):
    """取得資源檔案絕對路徑（支援 PyInstaller 打包）"""
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)
