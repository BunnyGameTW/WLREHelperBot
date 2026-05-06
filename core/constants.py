"""
純常數與工具函式
"""
import sys
import os

# 【核心設定】基準解析度
BASE_W, BASE_H = 1275, 755

# 視窗標題
WINDOW_TITLE = "飄流幻境Re:星之方舟"

# 遊戲執行檔名稱
GAME_EXE_NAME = "飄流幻境Re_星之方舟.exe"

# 預設比對門檻
THRESHOLD = 0.80

# 重連流程固定選服點擊座標
RECONNECT_SERVER_CLICK_POINT = (500, 50)

# 模板檔案對應
TEMPLATES_PATHS = {
    "battle_title": "battle_title.png",
    "btn_add": "btn_add.png",
    "btn_confirm": "btn_confirm.png",
    "btn_join": "btn_join.png",
    "in_battle": "in_battle.png",
    "energy_low": "energy_low.png",
    "energy_9": "energy_9.png",
    "disconnect_hint": "disconnect_hint.png",
    "btn_reconnect": "btn_reconnect.png",
    "btn_back_to_login": "btn_back_to_login.png",
    "check_exit": "check_exit.png",
    "multi_login": "multi_login.png",
    "custom_login": "custom_login.png",
    "btn_login_account": "btn_login_account.png",
    "select_server": "select_server.png",
    "select_character": "select_character.png",
    "login_game_button": "login_game_button.png",
    "pop_gift_box": "pop_gift_box.png",
    "start_game_announcement": "start_game_announcement.png",
    "announcement": "announcement.png",
    "dont_ask_today": "dont_ask_today.png",
    "btn_cross": "btn_cross.png",
    "btn_power_saving": "btn_power_saving.png",
    "btn_wander_on": "btn_wander_on.png",
    "btn_wander_off": "btn_wander_off.png",
    "btn_ai": "btn_ai.png",
    "btn_ai_off_in_battle": "btn_ai_off_in_battle.png",
        "update_resource": "update_resource.png",
    "login_from_other_place": "login_from_other_place.png",
}

# 平台專用配置檔名
CONFIG_FILE_PC = "bot_config_pc.json"
CONFIG_FILE_EMU = "bot_config_emu.json"


def resource_path(relative_path):
    """取得資源檔案絕對路徑（支援 PyInstaller 打包）"""
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)
