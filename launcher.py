"""
啟動器 - PC 模式（薄型入口）
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
from gui.pc_threads import BotControlThread  # noqa: F401
from gui.pc_ui import PCUIMixin
from gui.pc_config import PCConfigMixin
from gui.pc_display import PCDisplayMixin
from gui.pc_control import PCControlMixin
from gui.pc_log import PCLogMixin


class PCMainWindow(PCUIMixin, PCConfigMixin, PCDisplayMixin, PCControlMixin, PCLogMixin, QMainWindow):
    """PC 模式主視窗（透過 mixin 組合所有功能）"""

    def __init__(self):
        super().__init__()
        init_i18n("zh_TW")
        self.setWindowTitle(t("app_title", "女王的飄流小助手") + f" - PC v{APP_VERSION}")
        _s = QSettings("WLREPVEBot", "PCWindow")
        _geo = _s.value("geometry")
        if _geo:
            self.restoreGeometry(_geo)
        else:
            self.setGeometry(100, 100, 1300, 800)
        self.apply_app_icon()

        self.bot_thread = None
        self.is_running = False
        self.is_paused = False
        self.is_debug = False
        self.selected_windows = []
        self.window_map = {}
        self.config_dirty = False
        self.default_config = self._load_default_config()
        self.log_history = []
        self._pause_toggle_cooldown = 0.25
        self._last_pause_toggle_ts = 0.0
        self._is_initializing = True

        self.init_ui()
        self.update_ui_texts()
        self._original_config = deepcopy(self._collect_current_config())
        self._label_base_texts = {}
        self._checkbox_base_texts = {}
        self._widget_base_styles = {}
        self._is_initializing = False
        self.config_dirty = False
        if hasattr(self, "save_btn"):
            self.save_btn.setEnabled(False)
        if hasattr(self, "reset_btn"):
            self.reset_btn.setEnabled(False)
        if hasattr(self, "launch_save_btn"):
            self.launch_save_btn.setEnabled(False)
        if hasattr(self, "launch_reset_btn"):
            self.launch_reset_btn.setEnabled(False)
        self.update_current_config_display()
        self._update_run_action_guard()
        self.refresh_windows()


def main():
    import signal
    app = QApplication(sys.argv)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    window = PCMainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()