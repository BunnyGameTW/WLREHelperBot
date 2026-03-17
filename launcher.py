"""
啟動器 - PC 模式
整合 autoPVE 核心邏輯，提供 PC 模式專用的 GUI 介面
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
    QComboBox, QShortcut
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


class BotControlThread(QThread):
    """機器人控制線程 - PC 模式專用"""
    log_signal = pyqtSignal(str)

    def __init__(self, selected_windows, config):
        super().__init__()
        self.selected_windows = selected_windows
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
            config_override['mode'] = '1'
            config_override['target_windows'] = self.selected_windows

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


class PCMainWindow(QMainWindow):
    """PC 模式主窗口"""

    def __init__(self):
        super().__init__()

        # 初始化多語言
        init_i18n("zh_TW")

        self.setWindowTitle(t("app_title", "女王化身為無情的戰爭機器 小助手") + " - PC v1.0")
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

        self.init_ui()
        self.refresh_windows()

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
                "PC": {
                    "title": 0.80, "btn_add": 0.80, "btn_confirm": 0.80,
                    "btn_join": 0.80, "in_battle": 0.80, "energy_low": 0.90, "energy_9": 0.92
                }
            }
        }
        try:
            with open(resource_path("default_config_pc.json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
        try:
            with open(resource_path("default_config.json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return fallback

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
        self.setWindowTitle(t("app_title", "女王化身為無情的戰爭機器 小助手") + " - PC v1.0")

        # 標籤頁名稱
        self.tabs.setTabText(0, t("app_launch", "啟動"))
        self.tabs.setTabText(1, t("app_setting", "設定"))
        self.tabs.setTabText(2, t("app_console", "控制台"))
        self.tabs.setTabText(3, t("help_title", "說明"))

        # 語言標籤
        self.lang_label.setText(t("language_label", "語言") + " / Language:")

        # 啟動頁
        self.window_group.setTitle(t("select_game_window", "選擇遊戲窗口") + " (" + t("mode_pc", "單選") + ")")
        self.refresh_btn.setText(t("btn_refresh_window", "刷新視窗"))

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
        self.energy_check.setText(t("stop_waiting", "低活力時停止（不補充）"))

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

        self.save_btn.setText(t("config_change", "保存設定"))
        self.restore_btn.setText(t("btn_restore_defaults", "恢復預設"))

        # 控制台
        self.log_group.setTitle(t("error", "輸出日誌"))
        self.clear_log_btn.setText(t("btn_clear_log", "清空日誌"))

        # 說明
        self._update_help_text()

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

        # 窗口選擇 (單選模式)
        self.window_group = QGroupBox(t("select_game_window", "選擇遊戲窗口") + " (" + t("mode_pc", "單選") + ")")
        window_layout = QVBoxLayout()

        self.window_list = QListWidget()
        self.window_list.itemChanged.connect(self.on_window_selection_changed)
        window_layout.addWidget(self.window_list)

        button_layout = QHBoxLayout()
        self.refresh_btn = QPushButton(t("btn_refresh_window", "刷新視窗"))
        self.refresh_btn.clicked.connect(self.refresh_windows)
        button_layout.addWidget(self.refresh_btn)

        window_layout.addLayout(button_layout)
        self.window_group.setLayout(window_layout)
        layout.addWidget(self.window_group)

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
        default_wait = self.default_config.get("wait_times", {})
        for key, (i18n_key, fallback) in wait_names.items():
            spinner = QDoubleSpinBox()
            spinner.setRange(0.1, 120.0)
            spinner.setValue(default_wait.get(key, 1.0))
            spinner.setSingleStep(0.1)
            spinner.valueChanged.connect(self.on_config_changed)
            self.wait_spinners[key] = spinner
            label = QLabel(t(i18n_key, fallback) + ":")
            self.wait_labels[key] = label
            left_form.addRow(label, spinner)

        # 活力策略
        self.energy_label = QLabel(t("energy_strategy_config", "活力策略") + ":")
        self.energy_check = QCheckBox(t("stop_waiting", "低活力時停止（不補充）"))
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
        default_thresholds = self.default_config.get("thresholds", {}).get("PC", {})
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
            spinner.setValue(default_thresholds.get(key, 0.80))
            spinner.valueChanged.connect(self.on_config_changed)
            self.threshold_spinners[key] = spinner
            label = QLabel(t(i18n_key, fallback) + ":")
            self.threshold_labels[key] = label
            right_form.addRow(label, spinner)

        self.config_group_right.setLayout(right_form)
        right_column.addWidget(self.config_group_right)
        right_column.addStretch()

        columns_layout.addLayout(right_column)

        layout.addLayout(columns_layout)

        # === 保存按鈕 ===
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
【{t("help_content", "PC 模式使用說明")}】

1. {t("app_launch", "啟動")}
   - {t("help_tip3", "PC 模式請保持視窗可見")}
   - {t("help_steps_desc", "選擇視窗 → 調整設定 → 按下啟動")}

2. {t("app_setting", "設定")}
   - {t("help_config_desc", "可調整等待時間、閾值與活力策略")}

3. {t("help_shortcuts", "快捷鍵")}
   - {t("stop_command", "Ctrl+C - 停止程式")}
   - {t("pause_command", "Ctrl+P - 暫停/繼續")}
   - {t("debug_command", "Ctrl+D - 切換除錯")}

4. {t("help_principle_title", "運作原理")}
   {t("help_principle_desc", "透過畫面擷取與模板比對自動識別並點擊")}
        """)

    def refresh_windows(self):
        """刷新窗口列表"""
        if self.is_running:
            self.append_log("[WARN] 執行中不可刷新視窗")
            return

        self.refresh_btn.setEnabled(False)
        self.window_list.clear()
        self.window_map.clear()
        self.selected_windows.clear()

        if AUTOPVE_AVAILABLE:
            try:
                windows = autoPVE.find_pc_game_windows()
                self.window_map = dict(windows)
            except Exception as e:
                self.append_log(f"[ERROR] 刷新失敗: {e}")
                self.window_map = {}
        else:
            import win32gui
            windows = {}
            def enum_windows(hwnd, lParam):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title and "飄流幻境" in title:
                        windows[hwnd] = title
                return True
            try:
                win32gui.EnumWindows(enum_windows, None)
            except:
                pass
            self.window_map = windows

        for hwnd, title in self.window_map.items():
            display = f"{title} (HWND: {hwnd})"
            item = QListWidgetItem(display)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, hwnd)
            self.window_list.addItem(item)

        self.refresh_btn.setEnabled(True)
        self.start_btn.setEnabled(False)
        self.append_log(f"[DETECT] 找到 {len(self.window_map)} 個遊戲窗口")

    def on_window_selection_changed(self, item):
        """窗口選擇變更 - 單選模式：勾選一個時自動取消其他"""
        if item.checkState() == Qt.Checked:
            # 取消其他項目的勾選
            self.window_list.blockSignals(True)
            for i in range(self.window_list.count()):
                other = self.window_list.item(i)
                if other is not item:
                    other.setCheckState(Qt.Unchecked)
            self.window_list.blockSignals(False)

        self.selected_windows = []
        for i in range(self.window_list.count()):
            it = self.window_list.item(i)
            if it.checkState() == Qt.Checked:
                hwnd = it.data(Qt.UserRole)
                if hwnd is not None:
                    self.selected_windows.append(hwnd)

        self.start_btn.setEnabled(len(self.selected_windows) > 0 and not self.is_running)

    def _build_config(self):
        """從 UI 控件收集配置"""
        config = {
            "wait_times": {k: s.value() for k, s in self.wait_spinners.items()},
            "energy_strategy": self.energy_check.isChecked(),
            "thresholds": {
                "PC": {k: s.value() for k, s in self.threshold_spinners.items()}
            }
        }
        return config

    def on_start_stop(self):
        """啟動/停止"""
        if self.is_running:
            self.stop_bot()
        else:
            if len(self.selected_windows) == 0:
                QMessageBox.warning(self, "Warning", t("status_none_selected", "請至少選擇一個遊戲窗口"))
                return
            self.start_bot()

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
        self.window_list.setEnabled(False)
        self.status_label.setText(t("resumed", "執行中"))
        self.status_label.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px; border-radius: 4px;")

        self.set_config_editing_enabled(False)

        config = self._build_config()
        self.bot_thread = BotControlThread(self.selected_windows, config)
        self.bot_thread.log_signal.connect(self.append_log)
        self.bot_thread.finished.connect(self.on_bot_finished)
        self.bot_thread.start()
        self.append_log(f"[START] PC 模式已啟動，控制 {len(self.selected_windows)} 個窗口")

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
        self.window_list.setEnabled(True)
        self.status_label.setText(t("stopped", "已停止"))
        self.status_label.setStyleSheet("background-color: #FF6B6B; color: white; padding: 8px; border-radius: 4px;")

        self.set_config_editing_enabled(True)

        self.start_btn.setEnabled(len(self.selected_windows) > 0)
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

    def set_config_editing_enabled(self, enabled):
        """啟用/停用設定頁面編輯"""
        for spinner in self.wait_spinners.values():
            spinner.setEnabled(enabled)
        for spinner in self.threshold_spinners.values():
            spinner.setEnabled(enabled)
        self.energy_check.setEnabled(enabled)
        self.save_btn.setEnabled(enabled and self.config_dirty)
        self.restore_btn.setEnabled(enabled)

    def on_config_changed(self):
        """配置變更"""
        self.config_dirty = True
        self.save_btn.setEnabled(True)

    def save_config(self):
        """保存設定到 bot_config.json"""
        try:
            config_path = "bot_config.json"
            config_data = {}
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)

            config_data["wait_times"] = {k: s.value() for k, s in self.wait_spinners.items()}
            config_data["energy_strategy"] = self.energy_check.isChecked()

            if "thresholds" not in config_data:
                config_data["thresholds"] = {}
            config_data["thresholds"]["PC"] = {k: s.value() for k, s in self.threshold_spinners.items()}

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

            self.config_dirty = False
            self.save_btn.setEnabled(False)
            self.append_log("[CONFIG] " + t("config_saved", "設定已保存"))
        except Exception as e:
            self.append_log(f"[ERROR] 保存設定失敗: {e}")

    def restore_defaults(self):
        """恢復預設"""
        default_wait = self.default_config.get("wait_times", {})
        for key, spinner in self.wait_spinners.items():
            spinner.setValue(default_wait.get(key, 1.0))

        default_thresholds = self.default_config.get("thresholds", {}).get("PC", {})
        for key, spinner in self.threshold_spinners.items():
            spinner.setValue(default_thresholds.get(key, 0.80))

        self.energy_check.setChecked(self.default_config.get("energy_strategy", False))

        self.config_dirty = False
        self.save_btn.setEnabled(False)
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

    window = PCMainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
