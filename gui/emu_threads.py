"""
gui/emu_threads.py
EMU 模式工作執行緒：設備掃描（DetectThread）與機器人控制（BotControlThread）
"""

import time
from copy import deepcopy

from PyQt5.QtCore import QThread, pyqtSignal

from gui.shared import LOG_QUEUE, AUTOPVE_AVAILABLE, autoPVE


class DetectThread(QThread):
    """設備檢測線程 - 只偵測 LDPlayer 設備"""
    devices_found = pyqtSignal(list)

    def run(self):
        try:
            if AUTOPVE_AVAILABLE:
                from core.device_utils import is_ldplayer_device
                devices = autoPVE.connect_adb(quiet=True)
                result = []
                for d in devices:
                    # 只保留 LDPlayer 設備
                    if not is_ldplayer_device(d.serial):
                        continue
                    # 驗證設備是否仍然連線
                    try:
                        d.shell("echo ok")
                    except Exception:
                        continue
                    display_name = autoPVE.get_device_display_name(d)
                    result.append({
                        'serial': d.serial,
                        'name': display_name,
                        'device_obj': d
                    })
                self.devices_found.emit(result)
            else:
                self.devices_found.emit([])
        except Exception as e:
            print(f"[ERROR] 設備檢測失敗: {e}")
            self.devices_found.emit([])


class BotControlThread(QThread):
    """機器人控制線程 - EMU 模式專用"""
    log_signal = pyqtSignal(str)

    def __init__(self, selected_devices, config):
        super().__init__()
        self.selected_devices = selected_devices  # list of ppadb Device objects
        self.config = config
        self.running = False
        self.bots = []

    def run(self):
        self.running = True
        if not AUTOPVE_AVAILABLE:
            self.log_signal.emit("[ERROR] autoPVE 核心模組不可用")
            return

        try:
            autoPVE.set_log_queue(LOG_QUEUE)
            autoPVE.set_cmd_input_enabled(False)

            config_override = deepcopy(self.config)
            config_override['mode'] = '2'
            config_override['target_devices'] = self.selected_devices

            self.bots = autoPVE.main(
                from_gui=True,
                log_queue=LOG_QUEUE,
                config_override=config_override
            )

            # 等待所有 bot 線程完成
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
