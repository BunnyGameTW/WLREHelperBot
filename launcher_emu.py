"""
啟動器 - EMU 模式（薄型入口）
所有業務邏輯已拆分至 gui/ 子套件，本檔作為 PyInstaller 入口點。
"""

import sys
import warnings
from copy import deepcopy

warnings.filterwarnings("ignore", category=DeprecationWarning)
try:
    import PyQt5.sip
    if hasattr(PyQt5.sip, "setdestroyonexit"):
        PyQt5.sip.setdestroyonexit(False)
except Exception:
    pass

from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QSettings
from i18n import init_i18n, t

from gui.shared import APP_VERSION, LOG_QUEUE  # noqa: F401
from gui.emu_threads import DetectThread, BotControlThread  # noqa: F401
from gui.emu_ui import EmuUIMixin
from gui.emu_config import EmuConfigMixin
from gui.emu_display import EmuDisplayMixin
from gui.emu_control import EmuControlMixin
from gui.emu_log import EmuLogMixin


class EmuMainWindow(EmuUIMixin, EmuConfigMixin, EmuDisplayMixin, EmuControlMixin, EmuLogMixin, QMainWindow):
    """EMU 模式主視窗（透過 mixin 組合所有功能）"""

    def __init__(self):
        super().__init__()
        init_i18n("zh_TW")
        self.setWindowTitle(t("app_title", "女王的飄流小助手") + f" - EMU v{APP_VERSION}")
        _s = QSettings("WLREHelperBot", "EMUWindow")
        _geo = _s.value("geometry")
        if _geo:
            self.restoreGeometry(_geo)
        else:
            self.setGeometry(100, 100, 1400, 900)
        self.apply_app_icon()

        self.bot_thread = None
        self.is_running = False
        self.is_paused = False
        self.is_debug = False
        self.selected_devices = []
        self.selected_device_objects = {}
        self.device_map = {}
        self.config_dirty = False
        self.detect_thread = None
        self.log_history = []
        self._pause_toggle_cooldown = 0.25
        self._last_pause_toggle_ts = 0.0
        self._is_initializing = True

        self.default_config = self._load_default_config()
        self.current_config = {
            "wait_times": {
                "scan_interval": 1.0, "after_click": 0.1, "pop_window": 0.1,
                "battle_unlock": 1.0, "join_confirm": 0.1, "wait_battle_check": 30.0,
            },
            "energy_strategy": True,
            "auto_battle_enabled": True,
            "device_strategies": {},
            "device_auto_features": {},
            "thresholds_emu": {
                "battle_title": 0.70, "btn_add": 0.70, "btn_confirm": 0.70,
                "btn_join": 0.70, "in_battle": 0.70, "energy_low": 0.74, "energy_9": 0.95,
                "disconnect_hint": 0.70, "btn_reconnect": 0.70, "btn_back_to_login": 0.70,
                "multi_login": 0.70, "custom_login": 0.70,
                "btn_login_account": 0.70, "select_server": 0.70, "select_character": 0.70,
                "login_game_button": 0.70, "pop_gift_box": 0.70,
                "start_game_announcement": 0.70, "announcement": 0.70,
                "dont_ask_today": 0.70, "btn_cross": 0.70, "btn_power_saving": 0.70,
                "btn_wander_on": 0.70, "btn_wander_off": 0.70,
                "btn_ai": 0.70, "btn_ai_off_in_battle": 0.70,
                "update_resource": 0.70, "login_from_other_place": 0.70,
            },
            "disconnect": {
                "enabled": True,
                "same_screen_timeout": 45.0,
                "max_reconnect_attempts": 5,
                "action_cooldown": 1.0,
                "auto_feature_scan_interval": 0.6,
                "auto_feature_action_cooldown": 1.0,
                "in_game_confirm_timeout": 25.0,
                "check_game_open_interval_emu": 60.0,
                "pc_launch_wait_timeout": 25.0,
                "screen_hash_diff_threshold": 5.0,
                "screen_hash_interval": 1.0,
                "login_timeout": 120.0,
                "post_login_timeout": 45.0,
                "restart_game_enabled": True,
                "login_game_enabled": True,
                "auto_enable_features_enabled": True,
                "auto_enable_wander": True,
                "auto_enable_ai": True,
                "pc_exe_path": "",
                "emu_package_name": "",
            },
            "emulator_paths": {},
        }
        self._load_config()
        self._original_config = deepcopy(self.current_config)
        self._label_base_texts = {}
        self._checkbox_base_texts = {}
        self._widget_base_styles = {}

        self.init_ui()
        self.update_ui_texts()
        self._apply_config_to_ui()
        self._is_initializing = False
        self.config_dirty = False
        if hasattr(self, "save_btn"):
            self.save_btn.setEnabled(False)
        if hasattr(self, "reset_btn"):
            self.reset_btn.setEnabled(False)
        self._update_run_action_guard()
        self.refresh_devices()


def main():
    import signal
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    window = EmuMainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()