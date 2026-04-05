"""
gui/pc_threads.py
PC 模式機器人控制線程
"""

import time
from copy import deepcopy

from PyQt5.QtCore import QThread, pyqtSignal

from gui.shared import LOG_QUEUE, AUTOPVE_AVAILABLE

if AUTOPVE_AVAILABLE:
    import autoPVE


class BotControlThread(QThread):
    """機器人控制線程 - PC 模式專用"""
    log_signal = pyqtSignal(str)
    hwnd_changed_signal = pyqtSignal(int, int)  # (old_hwnd, new_hwnd)

    def __init__(self, selected_windows, config):
        super().__init__()
        self.selected_windows = selected_windows
        self.config = config
        self.running = False
        self.bots = []

    def _on_hwnd_changed(self, old_hwnd, new_hwnd):
        """bot 重新綁定 hwnd 時的回調，發送信號至 UI 線程。"""
        self.hwnd_changed_signal.emit(int(old_hwnd), int(new_hwnd))

    def run(self):
        self.running = True
        if not AUTOPVE_AVAILABLE:
            self.log_signal.emit("[ERROR] autoPVE 核心模組不可用")
            return

        try:
            autoPVE.set_log_queue(LOG_QUEUE)
            autoPVE.set_cmd_input_enabled(False)

            config_override = deepcopy(self.config)
            config_override['mode'] = '1'
            config_override['target_windows'] = self.selected_windows

            self.bots = autoPVE.main(
                from_gui=True,
                log_queue=LOG_QUEUE,
                config_override=config_override
            )

            for bot in self.bots:
                bot.on_hwnd_changed = self._on_hwnd_changed

            while self.running and self.bots and any(bot.is_alive() for bot in self.bots):
                time.sleep(0.1)
        except Exception as e:
            self.log_signal.emit(f"[ERROR] 執行失敗: {e}")

    def stop(self):
        self.running = False
        for bot in self.bots:
            try:
                bot.stop()
            except Exception:
                pass
