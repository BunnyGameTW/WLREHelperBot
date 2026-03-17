"""
啟動器 - EMU 模式
整合 autoPVE 核心邏輯，提供模擬器模式專用的 GUI 介面
"""

import sys
import os
import warnings
import json
import time
from queue import Queue, Empty
from copy import deepcopy

# 抑制 sipPyTypeDict 棄用警告
warnings.filterwarnings("ignore", category=DeprecationWarning)
try:
    import PyQt5.sip
    if hasattr(PyQt5.sip, 'setdestroyonexit'):
        PyQt5.sip.setdestroyonexit(False)
except:
    pass

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QTabWidget, QGroupBox, QFormLayout,
    QListWidget, QListWidgetItem, QTextEdit, QCheckBox, QDoubleSpinBox,
    QComboBox, QScrollArea, QShortcut, QLineEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon, QKeySequence

from i18n import init_i18n, t, set_language, get_i18n

# 載入 autoPVE 核心模組
try:
    import autoPVE
    AUTOPVE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Cannot import autoPVE: {e}")
    AUTOPVE_AVAILABLE = False

LOG_QUEUE = Queue(maxsize=1000)


def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)


# 模擬器啟動器進程關鍵字（非實際遊戲設備，應過濾掉）
EMU_LAUNCHER_KEYWORDS = [
    "launcher", "player", "multiplayer", "multi", "manager",
    "dnmultiplayer", "dnplayer", "mumuplayer", "mumumulti",
    "noxmulti", "bstweaker", "bluestacks_nxt"
]

# MuMu 常見 ADB 連接埠
MUMU_ADB_PORTS = [16384, 16416, 16448, 16480, 16512, 16544, 16576]


def _try_connect_mumu_ports(client):
    """嘗試連接 MuMu 模擬器的常見 ADB 埠"""
    import subprocess
    for port in MUMU_ADB_PORTS:
        addr = f"127.0.0.1:{port}"
        try:
            subprocess.run(
                ["adb", "connect", addr],
                capture_output=True, timeout=3
            )
        except Exception:
            pass


def _is_emu_launcher(device):
    """判斷設備是否為模擬器啟動器/管理器（非實際遊戲設備）"""
    serial = getattr(device, 'serial', str(device)).lower()
    # 啟動器通常不會有標準 ADB 埠格式
    # 透過 shell 取得 activity 判斷
    try:
        # 檢查 getprop 看是否有模擬器進程標記
        top_activity = device.shell("dumpsys activity activities | grep mResumedActivity").strip().lower()
        for kw in EMU_LAUNCHER_KEYWORDS:
            if kw in top_activity:
                return True
    except Exception:
        pass
    return False


class DetectThread(QThread):
    """設備檢測線程 - 使用 ADB 直接偵測以取得 ppadb Device 對象"""
    devices_found = pyqtSignal(list)

    def run(self):
        try:
            if AUTOPVE_AVAILABLE:
                # 先嘗試連接 MuMu 的 ADB 埠
                from ppadb.client import Client as AdbClient
                try:
                    client = AdbClient(host="127.0.0.1", port=5037)
                    _try_connect_mumu_ports(client)
                except Exception:
                    pass

                devices = autoPVE.connect_adb()
                result = []
                for d in devices:
                    # 驗證設備是否仍然連線
                    try:
                        d.shell("echo ok")
                    except Exception:
                        continue  # 跳過無回應的設備
                    # 過濾啟動器進程
                    if _is_emu_launcher(d):
                        continue
                    display_name = autoPVE.get_device_display_name(d)
                    result.append({
                        'serial': d.serial,
                        'name': display_name,
                        'device_obj': d
                    })
                self.devices_found.emit(result)
            else:
                from emulator.emulator_manager import EmulatorDeviceManager
                manager = EmulatorDeviceManager()
                devices = manager.detect_devices(force_refresh=True)
                self.devices_found.emit(devices)
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
                time.sleep(0.5)
        except Exception as e:
            self.log_signal.emit(f"[ERROR] 執行失敗: {e}")

    def stop(self):
        self.running = False
        for bot in self.bots:
            try:
                bot.stop()
            except Exception:
                pass


class EmuMainWindow(QMainWindow):
    """EMU 模式主窗口"""

    def __init__(self):
        super().__init__()

        # 初始化多語言
        init_i18n("zh_TW")

        self.setWindowTitle(t("app_title", "女王化身為無情的戰爭機器 小助手") + " - EMU v1.0")
        self.setGeometry(100, 100, 1400, 900)
        self.apply_app_icon()

        self.bot_thread = None
        self.is_running = False
        self.is_paused = False
        self.is_debug = False
        self.selected_devices = []
        self.selected_device_objects = {}  # serial -> ppadb Device
        self.device_map = {}
        self.config_dirty = False
        self.detect_thread = None

        self.default_config = self._load_default_config()

        # 設定相關屬性
        self.current_config = {
            "wait_times": {
                "scan_interval": 1.0,
                "after_click": 0.1,
                "pop_window": 0.1,
                "battle_unlock": 1.0,
                "join_confirm": 0.1,
                "wait_battle_check": 30.0
            },
            "energy_strategy": False,
            "device_strategies": {},
            "thresholds_emu": {
                "title": 0.70,
                "btn_add": 0.70,
                "btn_confirm": 0.70,
                "btn_join": 0.70,
                "in_battle": 0.70,
                "energy_low": 0.74,
                "energy_9": 0.88
            },
            "emulator_paths": {}
        }
        self._load_config()

        self.init_ui()
        self._apply_config_to_ui()
        self.refresh_devices()

    def apply_app_icon(self):
        """設置應用圖標"""
        try:
            icon_path = resource_path("app.ico")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except:
            pass

    def _load_default_config(self):
        """讀取預設配置"""
        fallback = {
            "wait_times": {
                "scan_interval": 1.0, "after_click": 0.1, "pop_window": 0.1,
                "battle_unlock": 1.0, "join_confirm": 0.1, "wait_battle_check": 30.0
            },
            "energy_strategy": False,
            "thresholds": {
                "EMU": {
                    "title": 0.70, "btn_add": 0.70, "btn_confirm": 0.70,
                    "btn_join": 0.70, "in_battle": 0.70, "energy_low": 0.74, "energy_9": 0.88
                }
            }
        }
        try:
            with open(resource_path("default_config_emu.json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
        try:
            with open(resource_path("default_config.json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return fallback

    def _load_config(self):
        """加載使用者配置"""
        try:
            config_path = "bot_config.json"
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                if "wait_times" in config_data:
                    self.current_config["wait_times"].update(config_data["wait_times"])
                if "energy_strategy" in config_data:
                    self.current_config["energy_strategy"] = config_data["energy_strategy"]
                if "device_strategies" in config_data:
                    self.current_config["device_strategies"] = config_data["device_strategies"]
                if "thresholds" in config_data and "EMU" in config_data["thresholds"]:
                    self.current_config["thresholds_emu"].update(config_data["thresholds"]["EMU"])
                if "emulator_paths" in config_data:
                    self.current_config["emulator_paths"] = config_data["emulator_paths"]
        except Exception as e:
            print(f"[WARN] 加載配置失敗: {e}")

    def _save_config(self):
        """保存配置"""
        try:
            config_path = "bot_config.json"
            config_data = {}
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)

            config_data["wait_times"] = self.current_config["wait_times"]
            config_data["energy_strategy"] = self.current_config["energy_strategy"]
            config_data["device_strategies"] = self.current_config["device_strategies"]

            if "thresholds" not in config_data:
                config_data["thresholds"] = {}
            config_data["thresholds"]["EMU"] = self.current_config["thresholds_emu"]

            # 保存模擬器路徑
            emu_paths = {}
            for key, path_input in self.emulator_path_inputs.items():
                path = path_input.text().strip()
                if path:
                    emu_paths[key] = path
            if emu_paths:
                config_data["emulator_paths"] = emu_paths

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

            self.append_log("[CONFIG] " + t("config_saved", "設定已保存"))
        except Exception as e:
            self.append_log(f"[ERROR] 保存設定失敗: {e}")

    def _apply_config_to_ui(self):
        """將載入的配置套用到 UI 控件"""
        emu_paths = self.current_config.get("emulator_paths", {})
        for key, path in emu_paths.items():
            if key in self.emulator_path_inputs:
                self.emulator_path_inputs[key].setText(path)

    def init_ui(self):
        """初始化 UI"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout()

        # === 頂部語言選擇欄 ===
        header_layout = QHBoxLayout()
        self.lang_label = QLabel(t("language_label", "語言") + " / Language:")
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["中文 (繁體) - zh_TW", "中文 (簡體) - zh_CN", "English - en"])
        self.lang_combo.currentIndexChanged.connect(self.on_language_changed)
        header_layout.addWidget(self.lang_label)
        header_layout.addWidget(self.lang_combo)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # === 標籤頁 ===
        self.tabs = QTabWidget()

        self.launch_tab = self.create_launch_tab()
        self.config_tab = self.create_config_tab()
        self.console_tab = self.create_console_tab()
        self.help_tab = self.create_help_tab()

        self.tabs.addTab(self.launch_tab, t("app_launch", "啟動"))
        self.tabs.addTab(self.config_tab, t("app_setting", "設定"))
        self.tabs.addTab(self.console_tab, t("app_console", "控制台"))
        self.tabs.addTab(self.help_tab, t("help_title", "說明"))

        main_layout.addWidget(self.tabs)

        # === 狀態欄 ===
        status_layout = QHBoxLayout()
        self.status_label = QLabel(t("status_ready", "準備就緒"))
        self.status_label.setStyleSheet("background-color: #90EE90; color: black; padding: 8px; border-radius: 4px;")
        self.status_label.setFont(QFont("Arial", 10, QFont.Bold))
        status_layout.addWidget(self.status_label)
        main_layout.addLayout(status_layout)

        central.setLayout(main_layout)

        # === 快捷鍵 ===
        QShortcut(QKeySequence("Ctrl+C"), self, self._shortcut_stop)
        QShortcut(QKeySequence("Ctrl+P"), self, self._shortcut_pause)
        QShortcut(QKeySequence("Ctrl+D"), self, self.on_debug)

        # === 定時器 ===
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.collect_logs)
        self.log_timer.start(200)

    def on_language_changed(self, index):
        """語言變更事件"""
        lang_map = {0: "zh_TW", 1: "zh_CN", 2: "en"}
        set_language(lang_map.get(index, "zh_TW"))
        self.update_ui_texts()
        self.append_log("[INFO] " + t("config_loaded", "語言已切換"))

    def update_ui_texts(self):
        """更新所有 UI 文字為當前語言"""
        self.setWindowTitle(t("app_title", "女王化身為無情的戰爭機器 小助手") + " - EMU v1.0")

        # 標籤頁
        self.tabs.setTabText(0, t("app_launch", "啟動"))
        self.tabs.setTabText(1, t("app_setting", "設定"))
        self.tabs.setTabText(2, t("app_console", "控制台"))
        self.tabs.setTabText(3, t("help_title", "說明"))

        self.lang_label.setText(t("language_label", "語言") + " / Language:")

        # 啟動頁
        self.device_group.setTitle(t("btn_select_device", "選擇設備"))
        self.select_all_checkbox.setText(t("select_all", "全選"))
        self.refresh_btn.setText(t("btn_refresh_device", "刷新設備"))

        if not self.is_running:
            self.start_btn.setText(t("btn_start", "啟動"))
        else:
            self.start_btn.setText(t("btn_stop", "停止"))

        if not self.is_paused:
            self.pause_btn.setText(t("btn_pause", "暫停"))
        else:
            self.pause_btn.setText(t("resumed", "繼續"))

        if not self.is_debug:
            self.debug_btn.setText(t("btn_debug", "除錯模式"))
        else:
            self.debug_btn.setText(t("debug_mode", "除錯模式") + " [ON]")

        # 設定頁
        self.config_group_left.setTitle(t("wait_time_config", "等待時間設定") + " (s)")
        self.config_group_right.setTitle(t("threshold_config", "辨識閾值設定"))

        wait_i18n_keys = {
            "scan_interval": "wait_scan_interval",
            "after_click": "wait_after_click",
            "pop_window": "wait_pop_window",
            "battle_unlock": "wait_battle_unlock",
            "join_confirm": "wait_join_confirm",
            "wait_battle_check": "wait_wait_battle_check"
        }
        for key, i18n_key in wait_i18n_keys.items():
            if key in self.wait_labels:
                self.wait_labels[key].setText(t(i18n_key, key) + ":")

        threshold_i18n_keys = {
            "title": "threshold_title",
            "btn_add": "threshold_btn_add",
            "btn_confirm": "threshold_btn_confirm",
            "btn_join": "threshold_btn_join",
            "in_battle": "threshold_in_battle",
            "energy_low": "threshold_energy_low",
            "energy_9": "threshold_energy_9"
        }
        for key, i18n_key in threshold_i18n_keys.items():
            if key in self.threshold_labels:
                self.threshold_labels[key].setText(t(i18n_key, key) + ":")

        self.energy_label.setText(t("energy_strategy_config", "活力策略") + ":")
        self.energy_check.setText(t("stop_waiting", "低活力時停止（不補充）"))

        self.device_energy_group.setTitle(t("device_strategy_config", "每台設備活力策略"))
        self.emu_path_group.setTitle("模擬器安裝路徑設定")

        self.save_btn.setText(t("config_change", "保存設定"))
        self.restore_btn.setText(t("btn_restore_defaults", "恢復預設"))

        # 控制台
        self.log_group.setTitle(t("error", "輸出日誌"))
        self.clear_log_btn.setText(t("btn_clear_log", "清空日誌"))

        # 說明
        self._update_help_text()

        # 設定顯示
        self.update_current_config_display()

        # 狀態欄
        if not self.is_running:
            self.status_label.setText(t("status_ready", "準備就緒"))
        elif self.is_paused:
            self.status_label.setText(t("paused", "已暫停"))
        else:
            self.status_label.setText(t("resumed", "執行中"))

    def create_launch_tab(self):
        """啟動標籤"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 設備選擇
        self.device_group = QGroupBox(t("btn_select_device", "選擇設備"))
        device_layout = QVBoxLayout()

        self.select_all_checkbox = QCheckBox(t("select_all", "全選"))
        self.select_all_checkbox.stateChanged.connect(self.toggle_select_all)
        self.select_all_checkbox.setEnabled(False)
        device_layout.addWidget(self.select_all_checkbox)

        self.device_list = QListWidget()
        self.device_list.itemChanged.connect(self.on_device_selection_changed)
        device_layout.addWidget(self.device_list)

        button_layout = QHBoxLayout()
        self.refresh_btn = QPushButton(t("btn_refresh_device", "刷新設備"))
        self.refresh_btn.clicked.connect(self.refresh_devices)
        button_layout.addWidget(self.refresh_btn)

        device_layout.addLayout(button_layout)
        self.device_group.setLayout(device_layout)
        layout.addWidget(self.device_group)

        # 控制按鈕
        control_layout = QHBoxLayout()

        self.start_btn = QPushButton(t("btn_start", "啟動"))
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-weight: bold;")
        self.start_btn.clicked.connect(self.on_start_stop)
        self.start_btn.setEnabled(False)
        control_layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton(t("btn_pause", "暫停"))
        self.pause_btn.setStyleSheet("background-color: #9E9E9E; color: #CCCCCC; padding: 10px; font-weight: bold;")
        self.pause_btn.clicked.connect(self.on_pause)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText(t("btn_pause", "暫停"))
        control_layout.addWidget(self.pause_btn)

        self.debug_btn = QPushButton(t("btn_debug", "除錯模式"))
        self.debug_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 10px; font-weight: bold;")
        self.debug_btn.clicked.connect(self.on_debug)
        control_layout.addWidget(self.debug_btn)

        layout.addLayout(control_layout)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def create_config_tab(self):
        """設定標籤 - 左右兩欄佈局"""
        widget = QWidget()
        layout = QVBoxLayout()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # === 左右兩欄 ===
        columns_layout = QHBoxLayout()

        # --- 左欄：等待時間 + 活力策略 ---
        left_column = QVBoxLayout()

        self.config_group_left = QGroupBox(t("wait_time_config", "等待時間設定") + " (s)")
        left_form = QFormLayout()

        self.wait_spinners = {}
        self.wait_labels = {}
        wait_names = {
            "scan_interval": ("wait_scan_interval", "辨識畫面間隔"),
            "after_click": ("wait_after_click", "點擊等待時間"),
            "pop_window": ("wait_pop_window", "確認視窗跳出等待"),
            "battle_unlock": ("wait_battle_unlock", "戰鬥結束判斷掃描"),
            "join_confirm": ("wait_join_confirm", "加入確認等待"),
            "wait_battle_check": ("wait_wait_battle_check", "等待戰鬥超時檢查")
        }
        for key, (i18n_key, fallback) in wait_names.items():
            spinner = QDoubleSpinBox()
            spinner.setRange(0.1, 120.0)
            spinner.setValue(self.current_config["wait_times"].get(key, 1.0))
            spinner.setSingleStep(0.1)
            spinner.valueChanged.connect(self.on_config_changed)
            self.wait_spinners[key] = spinner
            label = QLabel(t(i18n_key, fallback) + ":")
            self.wait_labels[key] = label
            left_form.addRow(label, spinner)

        # 活力策略
        self.energy_label = QLabel(t("energy_strategy_config", "活力策略") + ":")
        self.energy_check = QCheckBox(t("stop_waiting", "低活力時停止（不補充）"))
        self.energy_check.setChecked(self.current_config["energy_strategy"])
        self.energy_check.stateChanged.connect(self.on_config_changed)
        left_form.addRow(self.energy_label, self.energy_check)

        self.config_group_left.setLayout(left_form)
        left_column.addWidget(self.config_group_left)
        left_column.addStretch()

        columns_layout.addLayout(left_column)

        # --- 右欄：辨識閾值 ---
        right_column = QVBoxLayout()

        self.config_group_right = QGroupBox(t("threshold_config", "辨識閾值設定"))
        right_form = QFormLayout()

        self.threshold_spinners = {}
        self.threshold_labels = {}
        default_thresholds = self.default_config.get("thresholds", {}).get("EMU", {})
        threshold_names = {
            "title": ("threshold_title", "標題辨識閾值"),
            "btn_add": ("threshold_btn_add", "加號按鈕閾值"),
            "btn_confirm": ("threshold_btn_confirm", "確認按鈕閾值"),
            "btn_join": ("threshold_btn_join", "搜尋對手按鈕閾值"),
            "in_battle": ("threshold_in_battle", "戰鬥中閾值"),
            "energy_low": ("threshold_energy_low", "低活力閾值"),
            "energy_9": ("threshold_energy_9", "滿活力閾值")
        }
        for key, (i18n_key, fallback) in threshold_names.items():
            spinner = QDoubleSpinBox()
            spinner.setRange(0.5, 1.0)
            spinner.setDecimals(2)
            spinner.setSingleStep(0.01)
            spinner.setValue(self.current_config["thresholds_emu"].get(key, default_thresholds.get(key, 0.70)))
            spinner.valueChanged.connect(self.on_config_changed)
            self.threshold_spinners[key] = spinner
            label = QLabel(t(i18n_key, fallback) + ":")
            self.threshold_labels[key] = label
            right_form.addRow(label, spinner)

        self.config_group_right.setLayout(right_form)
        right_column.addWidget(self.config_group_right)
        right_column.addStretch()

        columns_layout.addLayout(right_column)

        scroll_layout.addLayout(columns_layout)

        # === 模擬器路徑 + 每台設備活力策略：左右兩欄 ===
        bottom_columns = QHBoxLayout()

        # --- 左欄：模擬器路徑設定 ---
        self.emu_path_group = QGroupBox("模擬器安裝路徑設定")
        emu_path_layout = QFormLayout()

        self.emulator_path_inputs = {}
        self.browse_buttons = {}
        emulator_names = {
            "bluestacks": "BlueStacks",
            "ldplayer": "LD Player",
            "nox": "Nox",
            "mumu": "MuMu"
        }

        for key, label_text in emulator_names.items():
            path_layout = QHBoxLayout()
            path_input = QLineEdit()
            path_input.setPlaceholderText(f"C:\\Program Files\\{label_text}")
            path_input.textChanged.connect(self.on_config_changed)
            self.emulator_path_inputs[key] = path_input
            path_layout.addWidget(path_input)

            browse_btn = QPushButton("[瀏覽]")
            browse_btn.setMaximumWidth(60)
            browse_btn.clicked.connect(lambda checked, k=key: self.browse_emulator_path(k))
            self.browse_buttons[key] = browse_btn
            path_layout.addWidget(browse_btn)

            emu_path_layout.addRow(label_text + ":", path_layout)

        self.emu_path_group.setLayout(emu_path_layout)
        bottom_columns.addWidget(self.emu_path_group)

        # --- 右欄：每台設備活力策略 ---
        self.device_energy_group = QGroupBox(t("device_strategy_config", "每台設備活力策略"))
        device_energy_layout = QVBoxLayout()

        self.device_energy_info = QLabel(t("device_strategy_hint", "先在啟動頁選擇設備，才可設定個別策略。"))
        self.device_energy_info.setStyleSheet("color: #666; font-size: 9pt;")
        device_energy_layout.addWidget(self.device_energy_info)

        self.device_energy_checks = {}
        self.device_energy_container = QWidget()
        self.device_energy_container_layout = QVBoxLayout(self.device_energy_container)
        device_energy_layout.addWidget(self.device_energy_container)

        self.device_energy_group.setLayout(device_energy_layout)
        bottom_columns.addWidget(self.device_energy_group)

        scroll_layout.addLayout(bottom_columns)

        # === 目前套用設定 ===
        current_config_group = QGroupBox(t("config_info", "目前套用的設定"))
        current_config_layout = QVBoxLayout()

        self.current_config_text = QTextEdit()
        self.current_config_text.setReadOnly(True)
        self.current_config_text.setMinimumHeight(220)
        self.current_config_text.setFont(QFont("Courier", 10))
        self.update_current_config_display()
        current_config_layout.addWidget(self.current_config_text)

        current_config_group.setLayout(current_config_layout)
        scroll_layout.addWidget(current_config_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        # === 保存/重置按鈕 ===
        button_layout = QHBoxLayout()

        self.save_btn = QPushButton(t("config_change", "保存設定"))
        self.save_btn.clicked.connect(self.save_config)
        self.save_btn.setEnabled(False)
        button_layout.addWidget(self.save_btn)

        self.restore_btn = QPushButton(t("btn_restore_defaults", "恢復預設"))
        self.restore_btn.clicked.connect(self.restore_defaults)
        button_layout.addWidget(self.restore_btn)

        layout.addLayout(button_layout)

        widget.setLayout(layout)
        return widget

    def update_current_config_display(self):
        """更新目前套用設定顯示"""
        threshold_display = {
            "title": t("threshold_title", "標題"),
            "btn_add": t("threshold_btn_add", "加號按鈕"),
            "btn_confirm": t("threshold_btn_confirm", "確認按鈕"),
            "btn_join": t("threshold_btn_join", "搜尋對手"),
            "in_battle": t("threshold_in_battle", "戰鬥中"),
            "energy_low": t("threshold_energy_low", "低活力"),
            "energy_9": t("threshold_energy_9", "滿活力")
        }

        wait_display = {
            "scan_interval": t("wait_scan_interval", "辨識間隔"),
            "after_click": t("wait_after_click", "點擊等待"),
            "pop_window": t("wait_pop_window", "視窗跳出"),
            "battle_unlock": t("wait_battle_unlock", "戰鬥判斷"),
            "join_confirm": t("wait_join_confirm", "加入確認"),
            "wait_battle_check": t("wait_wait_battle_check", "戰鬥超時檢查")
        }

        config_text = f"【{t('config_info', '目前設定')}】\n\n"
        config_text += f"{t('threshold_config', '辨識閾值')}:\n"
        for key, display_name in threshold_display.items():
            value = self.current_config["thresholds_emu"].get(key, 0.70)
            config_text += f"  • {display_name}: {value:.2f}\n"

        config_text += f"\n{t('wait_time_config', '等待時間')} (s):\n"
        for key, display_name in wait_display.items():
            value = self.current_config["wait_times"].get(key, 1.0)
            config_text += f"  • {display_name}: {value:.1f}\n"

        energy_text = t("stop_waiting", "停止不補充") if self.current_config["energy_strategy"] else t("auto_supplement", "自動補充")
        config_text += f"\n{t('energy_strategy_config', '活力策略')}: {energy_text}"

        self.current_config_text.setText(config_text)

    def update_device_energy_settings(self):
        """更新每台設備的活力策略設定"""
        for i in reversed(range(self.device_energy_container_layout.count())):
            w = self.device_energy_container_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        self.device_energy_checks.clear()

        if not self.selected_devices:
            empty_label = QLabel(t("device_strategy_hint", "尚未選擇任何設備。請先在「啟動」頁選擇設備。"))
            empty_label.setStyleSheet("color: #999;")
            self.device_energy_container_layout.addWidget(empty_label)
            return

        for device_serial in self.selected_devices:
            device_name = self.device_map.get(device_serial, {}).get('name', device_serial)

            check = QCheckBox(f"{device_name} - {t('stop_waiting', '停止不補充')}")
            is_checked = self.current_config["device_strategies"].get(device_serial, False)
            check.setChecked(is_checked)
            check.stateChanged.connect(self.on_config_changed)

            self.device_energy_checks[device_serial] = check
            self.device_energy_container_layout.addWidget(check)

    def create_console_tab(self):
        """控制台標籤"""
        widget = QWidget()
        layout = QVBoxLayout()

        self.log_group = QGroupBox(t("error", "輸出日誌"))
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier", 9))
        log_layout.addWidget(self.log_text)

        self.clear_log_btn = QPushButton(t("btn_clear_log", "清空日誌"))
        self.clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        log_layout.addWidget(self.clear_log_btn)

        self.log_group.setLayout(log_layout)
        layout.addWidget(self.log_group)

        widget.setLayout(layout)
        return widget

    def create_help_tab(self):
        """說明標籤"""
        widget = QWidget()
        layout = QVBoxLayout()

        self.help_text_widget = QTextEdit()
        self.help_text_widget.setReadOnly(True)
        self._update_help_text()
        layout.addWidget(self.help_text_widget)

        widget.setLayout(layout)
        return widget

    def _update_help_text(self):
        """更新說明文字"""
        self.help_text_widget.setText(f"""
【{t("help_content", "EMU 模式使用說明")}】

1. {t("app_launch", "啟動")}
   - {t("btn_refresh_device", "刷新設備")} → {t("select_all", "全選")} → {t("btn_start", "啟動")}

2. {t("app_setting", "設定")}
   - {t("help_config_desc", "可調整等待時間、閾值與活力策略")}

3. {t("help_shortcuts", "快捷鍵")}
   - {t("stop_command", "Ctrl+C - 停止程式")}
   - {t("pause_command", "Ctrl+P - 暫停/繼續")}
   - {t("debug_command", "Ctrl+D - 切換除錯")}

4. {t("help_principle_title", "運作原理")}
   {t("help_principle_desc", "透過畫面擷取與模板比對自動識別並點擊")}

【{t("help_tips", "小提示")}】
- {t("help_tip1", "首次使用可先調整閾值與等待時間")}
- {t("help_tip2", "若辨識失敗可調整閾值")}
        """)

    def refresh_devices(self):
        """刷新設備列表"""
        self.refresh_btn.setEnabled(False)
        self.device_list.clear()
        self.device_map.clear()
        self.selected_devices.clear()
        self.selected_device_objects.clear()
        self.append_log("[DETECT] 正在掃描設備...")

        self.detect_thread = DetectThread()
        self.detect_thread.devices_found.connect(self.on_devices_detected)
        self.detect_thread.start()

    def on_devices_detected(self, devices):
        """設備檢測完成"""
        self.device_map.clear()
        self.selected_device_objects.clear()

        for dev in devices:
            serial = dev.get('serial', 'unknown')
            name = dev.get('name', 'Unknown Device')
            device_obj = dev.get('device_obj', None)

            self.device_map[serial] = dev
            if device_obj is not None:
                self.selected_device_objects[serial] = device_obj

            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, serial)
            self.device_list.addItem(item)

        self.refresh_btn.setEnabled(True)
        self.select_all_checkbox.setEnabled(self.device_list.count() > 0)

        count = len(devices)
        self.append_log(f"[DETECT] 找到 {count} 台設備")

    def toggle_select_all(self, state):
        """全選/取消全選 - 僅回應用戶手動操作"""
        if not self.select_all_checkbox.hasFocus():
            return
        self.device_list.blockSignals(True)
        new_state = Qt.Checked if state != Qt.Unchecked else Qt.Unchecked
        for i in range(self.device_list.count()):
            self.device_list.item(i).setCheckState(new_state)
        self.device_list.blockSignals(False)
        # 確保全選框顯示正確狀態（非 PartiallyChecked）
        self.select_all_checkbox.blockSignals(True)
        self.select_all_checkbox.setCheckState(new_state)
        self.select_all_checkbox.blockSignals(False)
        self.on_device_selection_changed()

    def on_device_selection_changed(self, item=None):
        """設備選擇變更 - 同時更新全選複選框狀態"""
        self.selected_devices = []
        checked_count = 0
        total_count = self.device_list.count()

        for i in range(total_count):
            it = self.device_list.item(i)
            if it.checkState() == Qt.Checked:
                serial = it.data(Qt.UserRole)
                if serial:
                    self.selected_devices.append(serial)
                checked_count += 1

        # 更新全選複選框狀態
        self.select_all_checkbox.blockSignals(True)
        if total_count > 0 and checked_count == total_count:
            self.select_all_checkbox.setCheckState(Qt.Checked)
        else:
            self.select_all_checkbox.setCheckState(Qt.Unchecked)
        self.select_all_checkbox.blockSignals(False)

        self.update_device_energy_settings()
        self.start_btn.setEnabled(len(self.selected_devices) > 0 and not self.is_running)

    def on_start_stop(self):
        """啟動/停止"""
        if self.is_running:
            self.stop_bot()
        else:
            if len(self.selected_devices) == 0:
                QMessageBox.warning(self, "Warning", t("status_none_selected", "請至少選擇一台設備"))
                return
            self.start_bot()

    def _build_config(self):
        """從 UI 控件收集配置"""
        config = {
            "wait_times": {k: s.value() for k, s in self.wait_spinners.items()},
            "energy_strategy": self.energy_check.isChecked(),
            "thresholds": {
                "EMU": {k: s.value() for k, s in self.threshold_spinners.items()}
            }
        }
        device_configs = {}
        for serial, check in self.device_energy_checks.items():
            device_configs[serial] = check.isChecked()
        if device_configs:
            config["device_configs"] = device_configs
        return config

    def start_bot(self):
        """啟動機器人"""
        self.is_running = True
        self.is_paused = False
        self.is_debug = False
        self.start_btn.setText(t("btn_stop", "停止"))
        self.start_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px; font-weight: bold;")
        self.pause_btn.setEnabled(True)
        self.pause_btn.setText(t("btn_pause", "暫停"))
        self.pause_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 10px; font-weight: bold;")
        self.refresh_btn.setEnabled(False)
        self.status_label.setText(t("resumed", "執行中"))
        self.status_label.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px; border-radius: 4px;")

        # 鎖定啟動頁設備選擇
        self.set_launch_tab_enabled(False)
        self.set_config_editing_enabled(False)

        device_objects = []
        for serial in self.selected_devices:
            dev_obj = self.selected_device_objects.get(serial)
            if dev_obj is not None:
                device_objects.append(dev_obj)

        if not device_objects:
            self.append_log("[WARN] 無法取得設備對象，請重新刷新設備")
            self.stop_bot()
            return

        config = self._build_config()
        self.bot_thread = BotControlThread(device_objects, config)
        self.bot_thread.log_signal.connect(self.append_log)
        self.bot_thread.finished.connect(self.on_bot_finished)
        self.bot_thread.start()
        self.append_log(f"[START] EMU 模式已啟動，控制 {len(device_objects)} 台設備")

    def stop_bot(self):
        """停止機器人"""
        self.is_running = False
        if self.bot_thread:
            self.bot_thread.stop()
            self.bot_thread.wait()
            self.bot_thread = None
        self.start_btn.setText(t("btn_start", "啟動"))
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-weight: bold;")
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText(t("btn_pause", "暫停"))
        self.pause_btn.setStyleSheet("background-color: #9E9E9E; color: #CCCCCC; padding: 10px; font-weight: bold;")
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(t("stopped", "已停止"))
        self.status_label.setStyleSheet("background-color: #FF6B6B; color: white; padding: 8px; border-radius: 4px;")

        # 解鎖啟動頁 + 設定頁
        self.set_launch_tab_enabled(True)
        self.set_config_editing_enabled(True)

        self.start_btn.setEnabled(len(self.selected_devices) > 0)
        self.append_log("[STOP] 已停止")

    def on_bot_finished(self):
        """Bot 執行完畢時更新 UI"""
        if self.is_running:
            self.stop_bot()

    def on_pause(self):
        """暫停/繼續"""
        if not self.is_running:
            return
        self.is_paused = not self.is_paused
        if AUTOPVE_AVAILABLE:
            try:
                autoPVE.set_paused(self.is_paused)
            except Exception:
                pass
        if self.is_paused:
            self.pause_btn.setText(t("resumed", "繼續執行"))
            self.pause_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-weight: bold;")
            self.status_label.setText(t("paused", "已暫停"))
            self.status_label.setStyleSheet("background-color: #FFD54F; color: black; padding: 8px; border-radius: 4px;")
            self.append_log("[PAUSE] 已暫停")
        else:
            self.pause_btn.setText(t("btn_pause", "暫停"))
            self.pause_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 10px; font-weight: bold;")
            self.status_label.setText(t("resumed", "執行中"))
            self.status_label.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px; border-radius: 4px;")
            self.append_log("[RESUME] 已繼續")

    def on_debug(self):
        """除錯模式"""
        self.is_debug = not self.is_debug
        if AUTOPVE_AVAILABLE:
            try:
                autoPVE.set_debug_mode(self.is_debug)
            except Exception:
                pass
        if self.is_debug:
            self.debug_btn.setText(t("debug_mode", "除錯模式") + " [ON]")
            self.debug_btn.setStyleSheet("background-color: #FF5722; color: white; padding: 10px; font-weight: bold;")
            self.append_log("[DEBUG] 除錯模式已開啟")
        else:
            self.debug_btn.setText(t("btn_debug", "除錯模式"))
            self.debug_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 10px; font-weight: bold;")
            self.append_log("[DEBUG] 除錯模式已關閉")

    def _shortcut_stop(self):
        """Ctrl+C 快捷鍵 - 停止"""
        if self.is_running:
            self.stop_bot()

    def _shortcut_pause(self):
        """Ctrl+P 快捷鍵 - 暫停"""
        if self.is_running:
            self.on_pause()

    def browse_emulator_path(self, emulator_key):
        """瀏覽並選擇模擬器路徑"""
        from PyQt5.QtWidgets import QFileDialog
        emulator_names = {'bluestacks': 'BlueStacks', 'ldplayer': 'LD Player', 'nox': 'Nox', 'mumu': 'MuMu'}
        emulator_name = emulator_names.get(emulator_key, emulator_key)

        directory = QFileDialog.getExistingDirectory(self, f"選擇 {emulator_name} 安裝路徑", "")
        if directory:
            self.emulator_path_inputs[emulator_key].setText(directory)

    def set_launch_tab_enabled(self, enabled):
        """啟用/停用啟動頁控件（設備列表、全選、刷新）"""
        self.device_list.setEnabled(enabled)
        self.select_all_checkbox.setEnabled(enabled and self.device_list.count() > 0)
        self.refresh_btn.setEnabled(enabled)

    def set_config_editing_enabled(self, enabled):
        """啟用/停用設定頁面編輯"""
        for spinner in self.wait_spinners.values():
            spinner.setEnabled(enabled)
        for spinner in self.threshold_spinners.values():
            spinner.setEnabled(enabled)
        self.energy_check.setEnabled(enabled)
        for check in self.device_energy_checks.values():
            check.setEnabled(enabled)
        for path_input in self.emulator_path_inputs.values():
            path_input.setEnabled(enabled)
        for btn in self.browse_buttons.values():
            btn.setEnabled(enabled)
        self.save_btn.setEnabled(enabled and self.config_dirty)
        self.restore_btn.setEnabled(enabled)

    def on_config_changed(self):
        """配置變更"""
        # 更新 current_config
        for key, spinner in self.threshold_spinners.items():
            self.current_config["thresholds_emu"][key] = spinner.value()

        for key, spinner in self.wait_spinners.items():
            self.current_config["wait_times"][key] = spinner.value()

        self.current_config["energy_strategy"] = self.energy_check.isChecked()

        for serial, check in self.device_energy_checks.items():
            self.current_config["device_strategies"][serial] = check.isChecked()

        self.update_current_config_display()

        self.config_dirty = True
        self.save_btn.setEnabled(True)

    def save_config(self):
        """保存設定"""
        self.on_config_changed()
        self._save_config()
        self.config_dirty = False
        self.save_btn.setEnabled(False)

    def restore_defaults(self):
        """恢復預設"""
        default_wait = self.default_config.get("wait_times", {})
        for key, spinner in self.wait_spinners.items():
            spinner.setValue(default_wait.get(key, 1.0))

        default_thresholds = self.default_config.get("thresholds", {}).get("EMU", {})
        for key, spinner in self.threshold_spinners.items():
            spinner.setValue(default_thresholds.get(key, 0.70))

        self.energy_check.setChecked(self.default_config.get("energy_strategy", False))

        for check in self.device_energy_checks.values():
            check.setChecked(False)

        self.current_config["device_strategies"].clear()

        self.config_dirty = False
        self.save_btn.setEnabled(False)
        self.update_current_config_display()
        self.append_log("[CONFIG] " + t("btn_restore_defaults", "已恢復預設設定"))

    def _log_line_count(self):
        """取得目前日誌行數"""
        return self.log_text.document().blockCount()

    def append_log(self, msg):
        """添加日誌（超過 100 行自動清除舊紀錄）"""
        if self._log_line_count() > 100:
            self.log_text.clear()
        self.log_text.append(msg)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )

    def collect_logs(self):
        """收集日誌隊列"""
        while True:
            try:
                msg = LOG_QUEUE.get_nowait()
                self.append_log(msg)
            except Empty:
                break

    def closeEvent(self, event):
        """關閉事件"""
        if self.bot_thread:
            self.bot_thread.stop()
            self.bot_thread.wait()
        event.accept()


def main():
    """主入點"""
    app = QApplication(sys.argv)

    import signal
    def handle_sigint(*args):
        app.quit()

    signal.signal(signal.SIGINT, handle_sigint)

    window = EmuMainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
