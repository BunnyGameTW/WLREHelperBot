"""
PyQt5 GUI主程式 - 女王化身為無情的戰爭機器 小助手
支持多語言、快捷鍵控制、完整GUI配置與控制
"""
print("GUI script started...")

import sys
import signal
import json
import os
import threading
import time
from queue import Queue
import warnings
from copy import deepcopy

# 抑制 sipPyTypeDict 弃用警告
warnings.filterwarnings("ignore", category=DeprecationWarning)

# 修正 sipPyTypeDict 警告 - 在導入前設置
try:
    import PyQt5.sip
    PyQt5.sip.setdestroyonexit(False)
except:
    pass

# 覆蓋 excepthook 以防止退出時的警告
sys.excepthook = lambda *args: None

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QComboBox, QLabel, QTextEdit, QTabWidget, QLineEdit,
    QDoubleSpinBox, QCheckBox, QMessageBox, QProgressBar, QGroupBox,
    QFormLayout, QListWidget, QListWidgetItem, QScrollArea, QSizePolicy, QShortcut
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QTextCursor, QColor, QIcon, QKeySequence

# ===== 導入 autoPVE 模組 =====
try:
    import autoPVE
    AUTOPVE_AVAILABLE = True
except Exception as e:
    print(f"Warning: Cannot import autoPVE: {e}")
    AUTOPVE_AVAILABLE = False

def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)

# ========== 語言加載系統 ==========

def load_localization(language="zh_TW"):
    """加載多語言配置"""
    try:
        with open(resource_path("localization.json"), "r", encoding="utf-8") as f:
            localization = json.load(f)
        return localization.get(language, localization.get("zh_TW", {}))
    except Exception as e:
        print(f"Failed to load localization: {e}")
        return {}

def load_localization_with_validation(language="zh_TW"):
    """加載多語言配置並檢查缺失值，自動從 zh_TW 回退"""
    try:
        with open(resource_path("localization.json"), "r", encoding="utf-8") as f:
            localization = json.load(f)
        
        # 取得 zh_TW 作為後備語言
        fallback_lang = localization.get("zh_TW", {})
        selected_lang = localization.get(language, None)
        
        if selected_lang is None:
            print(f"[WARN] Language '{language}' not found, using 'zh_TW' as fallback")
            return fallback_lang
        
        # 檢查是否有任何鍵在選定語言中缺失
        missing_keys = set(fallback_lang.keys()) - set(selected_lang.keys())
        if missing_keys and language != "zh_TW":
            print(f"[WARN] Missing {len(missing_keys)} translations in '{language}'")
            # 合併：以 selected_lang 為主，缺失的從 fallback_lang 補充
            merged = fallback_lang.copy()
            merged.update(selected_lang)
            return merged
        
        return selected_lang
    except Exception as e:
        print(f"Failed to load localization: {e}")
        # 如果加載失敗，返回空字典（會導致 STRINGS.get() 使用預設值）
        return {}

# 全局語言對象
STRINGS = {}
APP_VERSION = "1.0.0"

# ========== 日誌系統 ==========
LOG_QUEUE = Queue(maxsize=1000)  # 日誌隊列
DEBUG_MODE = False
PAUSED = False
BOT_RUNNING = False
LOCK = threading.Lock()

# 日誌消息字典
LOG_MESSAGES = {
    "zh_TW": {
        "start": "[START]",
        "bot_running": "執行中",
        "debug_on": "[除錯] 開啟",
        "debug_off": "[除錯] 關閉",
        "paused": "[暫停] 已暫停",
        "resumed": "[暫停] 已繼續",
        "stopped": "[停止] 已停止",
        "search": "[搜尋]",
        "battle": "[戰鬥]",
        "energy": "[活力]",
        "click": "[點擊]",
        "error": "[錯誤]",
        "warn": "[警告]",
    },
    "zh_CN": {
        "start": "[START]",
        "bot_running": "执行中",
        "debug_on": "[调试] 开启",
        "debug_off": "[调试] 关闭",
        "paused": "[暂停] 已暂停",
        "resumed": "[暂停] 已继续",
        "stopped": "[停止] 已停止",
        "search": "[搜索]",
        "battle": "[战斗]",
        "energy": "[活力]",
        "click": "[点击]",
        "error": "[错误]",
        "warn": "[警告]",
    }
}

class BotControlThread(QThread):
    """機器人運行控制線程 - 集成 autoPVE 實際邏輯"""
    
    log_signal = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    pause_state_changed = pyqtSignal(bool)
    debug_state_changed = pyqtSignal(bool)
    
    def __init__(self, mode="1", devices=None, config=None):
        super().__init__()
        self.mode = mode
        self.devices = devices or []
        self.config = config or {}
        self.running = False
        self.paused = False
        self.debug_mode = False
        self.bots = []
        
    def run(self):
        """運行線程 - 使用實際的 autoPVE 邏輯"""
        self.running = True
        msg = STRINGS.get('bot_start', '開始循環...')
        self.log_signal.emit(f"[START] {msg}")
        
        # 檢查 autoPVE 是否可用
        if not AUTOPVE_AVAILABLE:
            self.log_signal.emit("[ERROR] autoPVE module not available, using simulation mode")
            self.run_simulation_mode()
            return
        
        try:
            # 為 autoPVE 設置日誌隊列
            autoPVE.set_log_queue(LOG_QUEUE)
            try:
                autoPVE.set_cmd_input_enabled(False)
                autoPVE.set_debug_mode(self.debug_mode)
                autoPVE.set_paused(self.paused)
            except Exception:
                pass
            
            # 準備配置
            config_override = self.config.copy() if self.config else {}
            config_override['mode'] = self.mode
            config_override['target_devices'] = self.devices
            
            # 從 autoPVE 啟動實際的 bot
            self.bots = autoPVE.main(from_gui=True, log_queue=LOG_QUEUE, config_override=config_override)
            
            # 等待所有 bot 線程完成
            while self.running and any(bot.is_alive() for bot in self.bots):
                time.sleep(0.5)
            
        except Exception as e:
            self.log_signal.emit(f"[ERROR] Bot execution failed: {e}")
            self.run_simulation_mode()
    
    def run_simulation_mode(self):
        """如果 autoPVE 不可用，進行模擬運行"""
        start_time = time.time()
        while self.running and (time.time() - start_time) < 60:
            if not self.paused:
                elapsed = int(time.time() - start_time)
                mode_label = STRINGS.get("platform_pc", "PC") if self.mode == "1" else STRINGS.get("platform_emu", "EMU")
                self.log_signal.emit(f"[{mode_label}] 執行中... ({elapsed}s)")
                time.sleep(2)
            else:
                time.sleep(0.5)

    def set_pause_state(self, paused, emit_log=True):
        self.paused = bool(paused)
        if AUTOPVE_AVAILABLE:
            try:
                autoPVE.set_paused(self.paused)
            except Exception:
                pass
        if emit_log:
            msg = STRINGS.get("paused", "Paused") if self.paused else STRINGS.get("resumed", "Running")
            self.log_signal.emit(f"[PAUSE] {msg}")
        self.pause_state_changed.emit(self.paused)

    def set_debug_state(self, enabled, emit_log=True):
        self.debug_mode = bool(enabled)
        if AUTOPVE_AVAILABLE:
            try:
                autoPVE.set_debug_mode(self.debug_mode)
            except Exception:
                pass
        if emit_log:
            state = STRINGS.get("debug_on", "ON") if self.debug_mode else STRINGS.get("debug_off", "OFF")
            debug_msg = STRINGS.get("debug_mode", "Debug Mode")
            self.log_signal.emit(f"[DBG] {debug_msg}: {state}")
            if self.debug_mode:
                shows = STRINGS.get('debug_shows', 'Debug details enabled')
                self.log_signal.emit(f"[DBG] {shows}")
        self.debug_state_changed.emit(self.debug_mode)

    def toggle_pause(self):
        return self.set_pause_state(not self.paused)
    
    def toggle_debug(self):
        return self.set_debug_state(not self.debug_mode)
    
    def stop(self):
        self.running = False
        # 停止所有 bot
        for bot in self.bots:
            if hasattr(bot, 'is_alive') and bot.is_alive():
                try:
                    bot.stop()
                except AttributeError:
                    self.log_signal.emit(f"[WARN] Bot object {type(bot).__name__} has no stop() method.")
                except Exception as e:
                    self.log_signal.emit(f"[ERROR] Failed to stop bot: {e}")

class MainGUI(QMainWindow):
    """主GUI窗口"""
    
    def __init__(self):
        super().__init__()
        global STRINGS
        self.bot_thread = None
        self.is_running = False
        self.is_paused = False
        self.is_debug = False
        self.config_dirty = False
        self._loading_config = False
        self.has_started = False
        self.active_mode = "1"
        self.last_loaded_config = None
        self.device_strategy_map = {}
        self.last_mode_index = 0
        self.current_language = "zh_TW"
        self.default_config = self.load_default_config()
        # 初始化語言字符串（使用驗證函數以檢查缺失值）
        STRINGS = load_localization_with_validation(self.current_language)
        self.init_ui()
        self.load_saved_config()
        self.setup_keyboard_listener()
        
        # 設置日誌收集計時器
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.collect_logs)
        self.log_timer.start(200)  # 每 200ms 檢查一次
        
        # 初始化按鈕狀態
        self.update_button_states()
        self.update_status_bar()
        
    def load_default_config(self):
        """讀取 default_config.json"""
        fallback = {
            "wait_times": {
                "scan_interval": 1.0,
                "after_click": 0.1,
                "pop_window": 0.1,
                "battle_unlock": 1.0,
                "join_confirm": 0.1,
                "wait_battle_check": 30.0
            },
            "energy_strategy": False,
            "thresholds": {
                "PC": {
                    "title": 0.80,
                    "btn_add": 0.80,
                    "btn_confirm": 0.80,
                    "btn_join": 0.80,
                    "in_battle": 0.80,
                    "energy_low": 0.90,
                    "energy_9": 0.92
                },
                "EMU": {
                    "title": 0.70,
                    "btn_add": 0.70,
                    "btn_confirm": 0.70,
                    "btn_join": 0.70,
                    "in_battle": 0.70,
                    "energy_low": 0.74,
                    "energy_9": 0.88
                }
            }
        }
        try:
            with open(resource_path("default_config.json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return fallback

    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle(f"{STRINGS.get('app_title', '女王化身為無情的戰爭機器 小助手')} v{APP_VERSION}")
        self.setGeometry(100, 100, 1300, 800)
        self.apply_app_icon()
        
        # 中心widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout()
        
        # ===== 1. 語言選擇欄 =====
        lang_layout = QHBoxLayout()
        self.lang_label = QLabel(STRINGS.get("language_label", "【語言】"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems([
            "繁體中文 (Traditional Chinese)",
            "簡體中文 (Simplified Chinese)",
            "English"
        ])
        self.lang_combo.setCurrentIndex(0)
        # 延遲連接信號，等待 UI 初始化完成
        self.lang_combo.currentIndexChanged.connect(self.change_language)
        lang_layout.addWidget(self.lang_label)
        lang_layout.addWidget(self.lang_combo)
        lang_layout.addStretch()
        main_layout.addLayout(lang_layout)
        
        # ===== 2. 標籤頁 =====
        self.tabs = QTabWidget()
        self.launch_tab = self.create_launch_tab()
        self.config_tab = self.create_config_tab()
        self.console_tab = self.create_console_tab()
        self.help_tab = self.create_help_tab()
        
        self.tabs.addTab(self.launch_tab, "啟動")
        self.tabs.addTab(self.config_tab, "設定")
        self.tabs.addTab(self.console_tab, "控制台")
        self.tabs.addTab(self.help_tab, "說明")
        
        main_layout.addWidget(self.tabs)
        
        # Keyboard shortcuts inside GUI
        self.setup_shortcuts()
        
        # ===== 3. 狀態欄 =====
        status_layout = QHBoxLayout()
        self.status_label = QLabel(STRINGS.get("apply_config", "準備就緒"))
        self.status_label.setStyleSheet("background-color: #90EE90; color: black; padding: 8px; border-radius: 4px;")
        self.status_label.setFont(QFont("Arial", 10, QFont.Bold))
        status_layout.addWidget(self.status_label)
        main_layout.addLayout(status_layout)
        
        central.setLayout(main_layout)
        
        # 在 init_ui 完成後，才進行第一次語言更新
        QTimer.singleShot(100, self.update_all_ui_language)
        if self.mode_combo.currentIndex() == 0:
            QTimer.singleShot(200, self.refresh_windows)
        self.on_mode_changed()
        
    def create_launch_tab(self):
        """建立啟動標籤"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 模式選擇
        self.mode_group = QGroupBox(STRINGS.get("mode_selection", "選擇模式"))
        mode_layout = QFormLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            STRINGS.get("mode_pc", "PC 模式"),
            STRINGS.get("mode_emu", "模擬器模式")
        ])
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        self.last_mode_index = self.mode_combo.currentIndex()
        mode_layout.addRow(self.mode_combo)
        self.mode_group.setLayout(mode_layout)
        layout.addWidget(self.mode_group)
        
        # 設備列表（EMU模式）
        self.device_group = QGroupBox(STRINGS.get("devices_detected", "選擇設備"))
        device_layout = QVBoxLayout()

        self.select_all_devices_checkbox = QCheckBox(STRINGS.get("select_all", "全選"))
        self.select_all_devices_checkbox.stateChanged.connect(self.toggle_select_all_devices)
        self.select_all_devices_checkbox.setEnabled(False)
        device_layout.addWidget(self.select_all_devices_checkbox)

        self.device_list = QListWidget()
        # self.device_list.setSelectionMode(QListWidget.MultiSelection)  # 改為使用複選框
        self.device_list.itemChanged.connect(self.on_device_selection_changed)
        
        # 初始化：會在刷新時填充
        self.refresh_devices_button = QPushButton(STRINGS.get("btn_refresh_device", "刷新設備"))
        self.refresh_devices_button.clicked.connect(self.refresh_devices)
        
        device_layout.addWidget(self.device_list)
        device_layout.addWidget(self.refresh_devices_button)
        self.device_group.setLayout(device_layout)
        # 保存設備信息用於識別
        self.device_map = {}  # 映射：顯示名稱 -> 設備對象
        layout.addWidget(self.device_group)
        
        # PC窗口選擇（初始隱藏，模式改變時顯示）
        self.pc_windows_group = QGroupBox(STRINGS.get("select_game_window", "選擇遊戲視窗"))
        pc_layout = QVBoxLayout()
        self.pc_windows_list = QListWidget()
        self.pc_windows_list.itemChanged.connect(self.on_pc_window_selection_changed)
        self.pc_window_map = {}
        self.refresh_windows_button = QPushButton(STRINGS.get("loading_templates", "刷新窗口"))
        self.refresh_windows_button.clicked.connect(self.refresh_windows)
        pc_layout.addWidget(self.pc_windows_list)
        pc_layout.addWidget(self.refresh_windows_button)
        self.pc_windows_group.setLayout(pc_layout)
        self.pc_windows_group.setVisible(False)
        layout.addWidget(self.pc_windows_group)
        
        # 按鈕
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton(STRINGS.get("btn_start", "啟動"))
        self.start_button.setStyleSheet("background-color: #4CAF50; color: white; padding: 12px; font-weight: bold; font-size: 13px;")
        self.start_button.clicked.connect(self.on_start_stop_clicked)
        
        # 三個控制按鈕
        self.debug_button = QPushButton(STRINGS.get("btn_debug", "除錯"))
        self.debug_button.setStyleSheet("background-color: #2196F3; color: white; padding: 12px; font-weight: bold; font-size: 12px;")
        self.debug_button.clicked.connect(self.toggle_debug)
        
        self.pause_button = QPushButton(STRINGS.get("btn_pause", "暫停"))
        self.pause_button.setStyleSheet("background-color: #FF9800; color: white; padding: 12px; font-weight: bold; font-size: 12px;")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.pause_button)
        button_layout.addWidget(self.debug_button)
        layout.addLayout(button_layout)
        
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def on_start_stop_clicked(self):
        """切換啟動/停止"""
        if self.is_running:
            self.stop_bot()
        else:
            if not self.can_start():
                if self.mode_combo.currentIndex() == 0:
                    self.append_log("[WARN] 請先選擇PC視窗")
                else:
                    self.append_log("[WARN] 請先選擇設備")
                return
            self.start_bot()

    def update_start_stop_button(self):
        if self.is_running:
            self.start_button.setEnabled(True)
            self.start_button.setText(STRINGS.get("btn_stop", "Stop"))
            self.start_button.setStyleSheet("background-color: #f44336; color: white; padding: 12px; font-weight: bold; font-size: 13px;")
            return

        can_start = self.can_start()
        self.start_button.setEnabled(can_start)
        self.start_button.setText(STRINGS.get("btn_start", "Start"))
        if can_start:
            self.start_button.setStyleSheet("background-color: #4CAF50; color: white; padding: 12px; font-weight: bold; font-size: 13px;")
        else:
            self.start_button.setStyleSheet("background-color: #9E9E9E; color: white; padding: 12px; font-weight: bold; font-size: 13px;")

    def update_launch_controls_locked(self):
        """啟動/暫停時鎖定控制"""
        locked = self.is_running
        self.mode_combo.setEnabled(not locked)
        self.device_list.setEnabled(not locked)
        self.select_all_devices_checkbox.setEnabled((not locked) and self.device_list.count() > 0)
        self.refresh_devices_button.setEnabled(not locked)
        self.pc_windows_list.setEnabled(not locked)
        self.refresh_windows_button.setEnabled(not locked)
        self.update_start_stop_button()
        self.update_status_bar()

    @pyqtSlot(bool)
    def on_pause_state_changed(self, paused):
        self.is_paused = bool(paused)
        self.update_button_states()
        self.update_launch_controls_locked()
        self.update_status_bar()

    @pyqtSlot(bool)
    def on_debug_state_changed(self, enabled):
        self.is_debug = bool(enabled)
        self.update_button_states()
        self.update_status_bar()

    def set_running_state(self, running):
        """更新啟動狀態"""
        self.is_running = bool(running)
        if not self.is_running:
            self.is_paused = False
            self.is_debug = False
            self.active_mode = "2" if self.mode_combo.currentIndex() == 1 else "1"
        self.update_start_stop_button()
        self.pause_button.setEnabled(self.is_running)
        self.debug_button.setEnabled(self.is_running)
        self.update_button_states()
        self.set_config_editing_enabled(not self.is_running)
        self.update_launch_controls_locked()
        self.update_status_bar()

    def toggle_select_all_devices(self, state):
        """全選/取消全選 設備"""
        check_state = Qt.Checked if state == Qt.Checked else Qt.Unchecked
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            item.setCheckState(check_state)
        self.update_device_strategy_list()
        self.update_start_stop_button()
        self.update_status_bar()

    def on_device_selection_changed(self, item):
        del item
        self.update_device_strategy_list()
        self.update_start_stop_button()
        self.update_status_bar()

    def on_pc_window_selection_changed(self, item):
        if item.checkState() == Qt.Checked:
            self.pc_windows_list.blockSignals(True)
            try:
                for i in range(self.pc_windows_list.count()):
                    other = self.pc_windows_list.item(i)
                    if other is not item and other.checkState() == Qt.Checked:
                        other.setCheckState(Qt.Unchecked)
            finally:
                self.pc_windows_list.blockSignals(False)
        self.update_start_stop_button()
        self.update_status_bar()
    
    def on_mode_changed(self):
        if self.is_running:
            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentIndex(self.last_mode_index)
            self.mode_combo.blockSignals(False)
            return
        self.last_mode_index = self.mode_combo.currentIndex()
        """當模式改變時更新UI"""
        is_pc_mode = self.mode_combo.currentIndex() == 0
        self.device_group.setVisible(not is_pc_mode)
        self.pc_windows_group.setVisible(is_pc_mode)
        if is_pc_mode and self.pc_windows_list.count() == 0:
            self.refresh_windows()
        if is_pc_mode and hasattr(self, "device_list"):
            self.device_list.clear()
            self.device_map.clear()
            self.select_all_devices_checkbox.setChecked(False)
            self.select_all_devices_checkbox.setEnabled(False)
        if (not is_pc_mode) and hasattr(self, "pc_windows_list"):
            self.pc_windows_list.clear()
            self.pc_window_map.clear()
        self.update_device_strategy_list()
        self.update_start_stop_button()
        self.update_status_bar()

    def apply_app_icon(self):
        icon_candidates = ["app.ico", "app.png"]
        for filename in icon_candidates:
            icon_path = resource_path(filename)
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
                break

    def get_selected_device_names(self):
        if not hasattr(self, "device_list"):
            return []
        names = []
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            if item.checkState() == Qt.Checked:
                names.append(item.text())
        return names

    def get_selected_device_serials(self):
        if not hasattr(self, "device_list"):
            return []
        serials = []
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            if item.checkState() != Qt.Checked:
                continue
            serial = item.data(Qt.UserRole)
            if not serial:
                device = self.device_map.get(item.text()) if hasattr(self, "device_map") else None
                if hasattr(device, "serial"):
                    serial = device.serial
                elif isinstance(device, dict):
                    serial = device.get("serial")
                else:
                    serial = item.text()
            serials.append(serial)
        return serials

    def get_device_display_name_for_serial(self, serial):
        if hasattr(self, "device_list"):
            for i in range(self.device_list.count()):
                item = self.device_list.item(i)
                if item.data(Qt.UserRole) == serial:
                    return item.text()
        return serial

    def update_device_strategy_list(self):
        if not hasattr(self, "device_strategy_group") or not hasattr(self, "device_list"):
            return
        is_emu_mode = self.mode_combo.currentIndex() == 1
        self.device_strategy_group.setVisible(True)

        self.device_strategy_list.blockSignals(True)
        try:
            self.device_strategy_list.clear()
            if is_emu_mode:
                for i in range(self.device_list.count()):
                    item = self.device_list.item(i)
                    if item.checkState() != Qt.Checked:
                        continue
                    display_name = item.text()
                    serial = item.data(Qt.UserRole)
                    if not serial:
                        device = self.device_map.get(display_name) if hasattr(self, "device_map") else None
                        if hasattr(device, "serial"):
                            serial = device.serial
                        elif isinstance(device, dict):
                            serial = device.get("serial")
                        else:
                            serial = display_name

                    strategy_value = self.device_strategy_map.get(serial, self.energy_checkbox.isChecked())
                    strategy_item = QListWidgetItem(display_name)
                    strategy_item.setFlags(strategy_item.flags() | Qt.ItemIsUserCheckable)
                    strategy_item.setCheckState(Qt.Checked if strategy_value else Qt.Unchecked)
                    strategy_item.setData(Qt.UserRole, serial)
                    self.device_strategy_list.addItem(strategy_item)

            self.device_strategy_list.setEnabled(is_emu_mode)

            self.device_strategy_hint.setVisible(True)
        finally:
            self.device_strategy_list.blockSignals(False)

    def on_device_strategy_changed(self, item):
        serial = item.data(Qt.UserRole)
        if not serial:
            return
        checked = item.checkState() == Qt.Checked
        if checked == self.energy_checkbox.isChecked():
            if serial in self.device_strategy_map:
                del self.device_strategy_map[serial]
        else:
            self.device_strategy_map[serial] = checked
        self.on_config_changed()

    def get_selected_pc_windows(self):
        if not hasattr(self, "pc_windows_list"):
            return []
        selected = []
        for i in range(self.pc_windows_list.count()):
            item = self.pc_windows_list.item(i)
            if item.checkState() == Qt.Checked:
                hwnd = self.pc_window_map.get(item.text())
                if hwnd is not None:
                    selected.append(hwnd)
        return selected

    def can_start(self):
        if self.is_running:
            return True
        is_emu_mode = self.mode_combo.currentIndex() == 1
        if is_emu_mode:
            return len(self.get_selected_device_names()) > 0
        return len(self.get_selected_pc_windows()) > 0

    def update_status_bar(self):
        if not hasattr(self, "status_label"):
            return
        if self.is_running:
            is_emu_mode = self.active_mode == "2"
        else:
            mode_index = self.mode_combo.currentIndex() if hasattr(self, "mode_combo") else 0
            is_emu_mode = mode_index == 1

        if self.is_running:
            if self.is_paused:
                state_text = STRINGS.get("status_paused_label", "Paused")
                bg_color = "#FFD54F"
                text_color = "black"
            else:
                state_text = STRINGS.get("status_running_label", "Running")
                bg_color = "#66BB6A"
                text_color = "white"
        else:
            if self.has_started:
                state_text = STRINGS.get("status_stopped_label", "Stopped")
                bg_color = "#EF5350"
                text_color = "white"
            else:
                state_text = STRINGS.get("status_ready", "Ready")
                bg_color = "#90EE90"
                text_color = "black"

        mode_text = STRINGS.get("platform_pc", "PC") if not is_emu_mode else STRINGS.get("platform_emu", "Emulator")
        if is_emu_mode:
            selected = self.get_selected_device_names()
            if selected:
                unit = STRINGS.get("status_devices_unit", "devices")
                count_text = f"{len(selected)} {unit}"
                shown = ", ".join(selected[:3])
                if len(selected) > 3:
                    shown = f"{shown}..."
                device_text = f"{count_text} {shown}".strip()
            else:
                device_text = STRINGS.get("status_none_selected", "None")
        else:
            selected_hwnds = self.get_selected_pc_windows()
            if selected_hwnds:
                unit = STRINGS.get("status_devices_unit", "devices")
                count_text = f"{len(selected_hwnds)} {unit}"
                names = []
                for i in range(self.pc_windows_list.count()):
                    item = self.pc_windows_list.item(i)
                    if item.checkState() == Qt.Checked:
                        names.append(item.text())
                shown = ", ".join(names[:2])
                if len(names) > 2:
                    shown = f"{shown}..."
                device_text = f"{count_text} {shown}".strip()
            else:
                device_text = STRINGS.get("status_none_selected", "None")

        debug_text = STRINGS.get("debug_on", "ON") if self.is_debug else STRINGS.get("debug_off", "OFF")
        status_text = (
            f"{STRINGS.get('status_state_label', 'State')}: {state_text} | "
            f"{STRINGS.get('status_mode_label', 'Mode')}: {mode_text} | "
            f"{STRINGS.get('status_device_label', 'Devices')}: {device_text} | "
            f"{STRINGS.get('status_debug_label', 'Debug')}: {debug_text}"
        )
        self.status_label.setText(status_text)
        self.status_label.setStyleSheet(
            f"background-color: {bg_color}; color: {text_color}; padding: 8px; border-radius: 4px;"
        )

    def set_config_editing_enabled(self, enabled):
        if hasattr(self, "wait_config"):
            for spin in self.wait_config.values():
                spin.setEnabled(enabled)
        if hasattr(self, "energy_checkbox"):
            self.energy_checkbox.setEnabled(enabled)
        if hasattr(self, "device_strategy_list"):
            self.device_strategy_list.setEnabled(enabled)
        if hasattr(self, "threshold_config"):
            for platform in self.threshold_config.values():
                for spin in platform.values():
                    spin.setEnabled(enabled)
        if not hasattr(self, "save_button"):
            return
        if not enabled:
            self.save_button.setEnabled(False)
            self.save_button.setStyleSheet("background-color: #9E9E9E; color: white; padding: 8px 14px; font-size: 12px;")
            if hasattr(self, "restore_defaults_button"):
                self.restore_defaults_button.setEnabled(False)
                self.restore_defaults_button.setStyleSheet("background-color: #9E9E9E; color: white; padding: 8px 14px; font-size: 12px;")
            if hasattr(self, "reset_changes_button"):
                self.reset_changes_button.setEnabled(False)
                self.reset_changes_button.setStyleSheet("background-color: #9E9E9E; color: white; padding: 8px 14px; font-size: 12px;")
        else:
            self.update_save_button_state()
            if hasattr(self, "restore_defaults_button"):
                self.restore_defaults_button.setEnabled(True)
                self.restore_defaults_button.setStyleSheet("background-color: #607D8B; color: white; padding: 8px 14px; font-size: 12px;")
            if hasattr(self, "reset_changes_button"):
                self.reset_changes_button.setEnabled(True)
                self.reset_changes_button.setStyleSheet("background-color: #9E9E9E; color: white; padding: 8px 14px; font-size: 12px;")

    def update_save_button_state(self):
        if not hasattr(self, "save_button"):
            return
        if self.config_dirty:
            self.save_button.setEnabled(True)
            self.save_button.setText(STRINGS.get("config_change", "Save Settings"))
            self.save_button.setStyleSheet("background-color: #FF9800; color: white; padding: 8px 14px; font-size: 12px;")
        else:
            self.save_button.setEnabled(False)
            self.save_button.setText(STRINGS.get("config_saved", "Settings Saved"))
            self.save_button.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 14px; font-size: 12px;")
        
    def create_config_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)

        self.config_info_label = QLabel(STRINGS.get("config_info", "Current Settings"))
        self.config_info_label.setStyleSheet("background-color: #E3F2FD; padding: 10px; border-radius: 4px; font-weight: bold;")
        self.config_info_label.setWordWrap(True)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QHBoxLayout()
        scroll_layout.setSpacing(12)

        left_column = QVBoxLayout()
        middle_column = QVBoxLayout()
        right_column = QVBoxLayout()
        left_column.setSpacing(10)
        middle_column.setSpacing(10)
        right_column.setSpacing(10)

        # Wait times
        self.wait_group = QGroupBox(STRINGS.get("wait_time_config", "Wait Time Settings"))
        wait_layout = QFormLayout()
        self.wait_config = {}
        self.wait_labels = {}
        default_wait_times = self.default_config.get("wait_times", {})
        for key, value in default_wait_times.items():
            spin = QDoubleSpinBox()
            spin.setValue(float(value))
            spin.setSingleStep(0.1)
            spin.setRange(0, 120)
            spin.valueChanged.connect(self.on_config_changed)
            self.wait_config[key] = spin
            label_text = STRINGS.get(f"wait_{key}", key)
            label = QLabel(f"{label_text}")
            self.wait_labels[key] = label
            wait_layout.addRow(label, spin)
        self.wait_group.setLayout(wait_layout)
        left_column.addWidget(self.wait_group)

        # Energy strategy
        self.energy_group = QGroupBox(STRINGS.get("energy_strategy_config", "Energy Strategy"))
        energy_layout = QFormLayout()
        self.energy_checkbox = QCheckBox(STRINGS.get("stop_waiting", "Stop and wait when energy is low"))
        self.energy_checkbox.stateChanged.connect(self.on_config_changed)
        self.energy_checkbox.stateChanged.connect(self.update_device_strategy_list)
        self.energy_desc_label = QLabel(f"{STRINGS.get('energy_description', 'When energy is low')}:")
        energy_layout.addRow(self.energy_desc_label, self.energy_checkbox)
        self.energy_group.setLayout(energy_layout)
        left_column.addWidget(self.energy_group)

        # Per-device energy strategy (Emulator mode)
        self.device_strategy_group = QGroupBox(STRINGS.get("device_strategy_config", "Per-device Energy Strategy"))
        device_strategy_layout = QVBoxLayout()
        hint_text = STRINGS.get(
            "device_strategy_hint",
            "Select devices in Launch tab to configure per-device strategy."
        )
        explain_text = STRINGS.get(
            "device_strategy_explain",
            "Checked = stop and wait; unchecked = auto recovery."
        )
        self.device_strategy_hint = QLabel(f"{hint_text}\n{explain_text}")
        self.device_strategy_hint.setStyleSheet("color: #666;")
        self.device_strategy_hint.setWordWrap(True)
        self.device_strategy_list = QListWidget()
        self.device_strategy_list.itemChanged.connect(self.on_device_strategy_changed)
        device_strategy_layout.addWidget(self.device_strategy_hint)
        device_strategy_layout.addWidget(self.device_strategy_list)
        self.device_strategy_group.setLayout(device_strategy_layout)
        left_column.addWidget(self.device_strategy_group)

        # Thresholds
        self.threshold_group = QGroupBox(STRINGS.get("threshold_config", "Threshold Settings"))
        threshold_layout = QVBoxLayout()
        self.threshold_config = {"PC": {}, "EMU": {}}
        self.threshold_labels = {"PC": {}, "EMU": {}}
        default_thresholds = self.default_config.get("thresholds", {})
        for platform in ["PC", "EMU"]:
            platform_group = QGroupBox(platform)
            platform_layout = QFormLayout()
            for key, value in default_thresholds.get(platform, {}).items():
                spin = QDoubleSpinBox()
                spin.setDecimals(2)
                spin.setSingleStep(0.01)
                spin.setRange(0.0, 1.0)
                spin.setValue(float(value))
                spin.valueChanged.connect(self.on_config_changed)
                self.threshold_config[platform][key] = spin
                label_text = STRINGS.get(f"threshold_{key}", key)
                label = QLabel(f"{label_text}")
                self.threshold_labels[platform][key] = label
                platform_layout.addRow(label, spin)
            platform_group.setLayout(platform_layout)
            threshold_layout.addWidget(platform_group)
        self.threshold_group.setLayout(threshold_layout)
        middle_column.addWidget(self.threshold_group)

        # Current config display
        right_column.addWidget(self.config_info_label)

        left_column.addStretch()
        middle_column.addStretch()
        right_column.addStretch()
        left_container = QWidget()
        left_container.setLayout(left_column)
        left_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        middle_container = QWidget()
        middle_container.setLayout(middle_column)
        middle_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        right_container = QWidget()
        right_container.setLayout(right_column)
        right_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        scroll_layout.addWidget(left_container)
        scroll_layout.addWidget(middle_container)
        scroll_layout.addWidget(right_container)
        scroll_layout.setStretch(0, 1)
        scroll_layout.setStretch(1, 1)
        scroll_layout.setStretch(2, 1)
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)

        button_layout = QHBoxLayout()
        self.save_button = QPushButton(STRINGS.get("config_change", "Save Settings"))
        self.save_button.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px 14px; font-size: 12px;")
        self.save_button.clicked.connect(self.save_config)
        self.save_button.setEnabled(False)
        self.restore_defaults_button = QPushButton(STRINGS.get("btn_restore_defaults", "恢復預設並儲存"))
        self.restore_defaults_button.setStyleSheet("background-color: #607D8B; color: white; padding: 8px 14px; font-size: 12px;")
        self.restore_defaults_button.clicked.connect(self.restore_defaults_and_save)
        self.reset_changes_button = QPushButton(STRINGS.get("btn_reset_changes", "重置操作"))
        self.reset_changes_button.setStyleSheet("background-color: #9E9E9E; color: white; padding: 8px 14px; font-size: 12px;")
        self.reset_changes_button.clicked.connect(self.reset_unsaved_changes)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.restore_defaults_button)
        button_layout.addWidget(self.reset_changes_button)
        button_layout.insertStretch(0, 1)
        layout.addLayout(button_layout)

        widget.setLayout(layout)
        return widget

    def create_console_tab(self):
        """建立控制台標籤"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 快捷鍵幫助
        help_text_content = (
            f"{STRINGS.get('help_shortcuts', '快捷鍵')}:\n"
            f"Ctrl+D - {STRINGS.get('debug_command', '開啟/關閉除錯模式').replace('Ctrl+D - ', '')}\n"
            f"Ctrl+P - {STRINGS.get('pause_command', '暫停/繼續偵測').replace('Ctrl+P - ', '')}\n"
            f"Ctrl+C - {STRINGS.get('stop_command', '停止腳本').replace('Ctrl+C - ', '')}\n"
        )
        self.help_text = QLabel(help_text_content)
        self.help_text.setStyleSheet("background-color: #e3f2fd; padding: 10px; border-radius: 4px;")
        layout.addWidget(self.help_text)
        
        # 日誌輸出
        log_label = QLabel(STRINGS.get("error", "運行日誌"))
        log_label.setObjectName("log_label")
        layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier New", 9))
        self.log_text.setStyleSheet("background-color: #f5f5f5; color: #333;")
        layout.addWidget(self.log_text)
        
        # 清空日誌
        self.clear_button = QPushButton(STRINGS.get("wait_time_inputs", "清空日誌"))
        self.clear_button.clicked.connect(lambda: self.log_text.clear())
        layout.addWidget(self.clear_button)
        
        widget.setLayout(layout)
        return widget
    
    def create_help_tab(self):
        """建立說明標籤"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        
        # 功能簡介
        features_text = (
            f"<b>{STRINGS.get('help_content', '功能簡介')}</b><br><br>"
            f"{STRINGS.get('help_features', '軟體支援兩種執行模式')}:<br>"
            f"• {STRINGS.get('help_pc_mode', 'PC 模式')}<br>"
            f"• {STRINGS.get('help_emu_mode', '模擬器模式')}<br><br>"
            f"<b>{STRINGS.get('help_principle_title', '運作原理')}</b><br>"
            f"{STRINGS.get('help_principle_desc', '透過畫面擷取與模板比對自動操作。')}<br><br>"
            f"<b>{STRINGS.get('help_steps_title', '詳細操作')}</b><br>"
            f"{STRINGS.get('help_steps_desc', '1. 選模式 2. 選設備/視窗 3. 設定參數 4. 啟動')}<br><br>"
            f"<b>{STRINGS.get('help_shortcuts', '快捷鍵')}</b><br>"
            f"• Ctrl+D: {STRINGS.get('help_debug', '切換除錯模式')}<br>"
            f"• Ctrl+P: {STRINGS.get('help_pause', '暫停或繼續')}<br>"
            f"• Ctrl+C: {STRINGS.get('help_stop', '停止程式')}<br><br>"
            f"<b>{STRINGS.get('help_config', '配置設定')}</b><br>"
            f"{STRINGS.get('help_config_desc', '在配置頁籤可以調整各項參數')}<br><br>"
            f"<b>{STRINGS.get('help_tips', '使用建議')}</b><br>"
            f"• {STRINGS.get('help_tip1', '首次執行時進行初始設定')}<br>"
            f"• {STRINGS.get('help_tip2', '如遇偵測失誤可微調門檻')}<br>"
            f"• {STRINGS.get('help_tip3', 'PC模式執行時保持視窗可見')}<br><br>"
            f"<b>{STRINGS.get('version_label', '版本')}</b>: v{APP_VERSION}"
        )
        
        self.help_content_label = QLabel()
        self.help_content_label.setText(features_text)
        self.help_content_label.setWordWrap(True)
        self.help_content_label.setStyleSheet("padding: 10px; line-height: 1.8;")
        scroll_layout.addWidget(self.help_content_label)
        scroll_layout.addStretch()
        
        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        widget.setLayout(layout)
        return widget
    
    def toggle_debug(self):
        if self.bot_thread:
            self.bot_thread.toggle_debug()
        
    def toggle_pause(self):
        """切換暫停"""
        if self.bot_thread:
            self.bot_thread.toggle_pause()
        
    def start_bot(self):
        """啟動機器人"""
        global BOT_RUNNING
        
        BOT_RUNNING = True
        self.has_started = True
        self.is_paused = False
        self.is_debug = False
        self.set_running_state(True)
        
        mode = "2" if self.mode_combo.currentIndex() == 1 else "1"
        self.active_mode = mode
        
        # 準備配置數據（從 GUI 控件收集）
        config = {}
        if hasattr(self, 'wait_config'):
            config['wait_times'] = {
                key: spin.value() for key, spin in self.wait_config.items()
            }
        if hasattr(self, 'energy_checkbox'):
            config['energy_strategy'] = self.energy_checkbox.isChecked()
        if hasattr(self, 'threshold_config'):
            config['thresholds'] = {
                platform: {k: spin.value() for k, spin in self.threshold_config[platform].items()}
                for platform in self.threshold_config
            }
        
        # 啟動 bot 線程，傳遞配置和設備信息
        selected_devices = []
        if mode == "2" and hasattr(self, 'device_list'):
            for i in range(self.device_list.count()):
                item = self.device_list.item(i)
                if item.checkState() == Qt.Checked:
                    serial = item.data(Qt.UserRole)
                    if not serial:
                        serial = item.text()
                    device = self.device_map.get(serial)
                    if device:
                        selected_devices.append(device)
            
            if not selected_devices:
                self.append_log("[WARN] 未選擇任何設備來執行。")
                self.stop_bot() # 停止以重設按鈕狀態
                return
            selected_serials = []
            for device in selected_devices:
                serial = getattr(device, "serial", None)
                if not serial:
                    serial = str(device)
                selected_serials.append(serial)
            device_configs = {
                serial: self.device_strategy_map[serial]
                for serial in selected_serials
                if serial in self.device_strategy_map
            }
            if device_configs:
                config["device_configs"] = device_configs
        elif mode == "1":
            selected_windows = self.get_selected_pc_windows()
            if not selected_windows:
                self.append_log("[WARN] 未選擇任何PC視窗來執行。")
                self.stop_bot()
                return
            config["target_windows"] = selected_windows
        
        self.bot_thread = BotControlThread(mode=mode, devices=selected_devices, config=config)
        self.bot_thread.log_signal.connect(self.append_log)
        self.bot_thread.pause_state_changed.connect(self.on_pause_state_changed)
        self.bot_thread.debug_state_changed.connect(self.on_debug_state_changed)
        self.bot_thread.finished.connect(self.on_bot_thread_finished)
        self.bot_thread.start()
        
        self.update_status_bar()
        self.append_log("[START] 機器人已啟動")
        
    def stop_bot(self):
        """停止機器人"""
        global BOT_RUNNING
        
        self.is_running = False
        BOT_RUNNING = False
        if self.bot_thread:
            self.bot_thread.stop()
            self.bot_thread.wait()
        self.bot_thread = None
        self.set_running_state(False)
        self.update_status_bar()
        self.append_log(f"[STOP] {STRINGS.get('stopped', 'Stopped')}")
        
    def on_bot_thread_finished(self):
        """Bot 蝺?擐活?湔 UI"""
        if self.is_running:
            self.set_running_state(False)
        self.bot_thread = None

    def setup_keyboard_listener(self):
        """設置鍵盤監聽器"""
        def keyboard_listener():
            try:
                import keyboard as kb
                while True:
                    if kb.is_pressed('ctrl+d'):
                        if self.is_running and self.bot_thread:
                            self.bot_thread.toggle_debug()
                        time.sleep(0.5)
                    elif kb.is_pressed('ctrl+p'):
                        if self.is_running and self.bot_thread:
                            self.bot_thread.toggle_pause()
                        time.sleep(0.5)
                    else:
                        time.sleep(0.1)
            except ImportError:
                self.append_log("[WARN] keyboard module not installed")
        
        listener_thread = threading.Thread(target=keyboard_listener, daemon=True)
        listener_thread.start()
        
    def update_config_info_label(self, config):
        wait_times = config.get("wait_times", {})
        energy_str = STRINGS.get("stop_waiting", "Stop and wait") if config.get("energy_strategy") else STRINGS.get("auto_supplement", "Auto recovery")
        wait_times_str = "\n".join(
            [f"  {STRINGS.get(f'wait_{k}', k)}: {wait_times.get(k)}" for k in self.wait_config.keys()]
        )
        device_configs = config.get("device_configs", {}) or {}
        device_config_text = ""
        if device_configs:
            lines = []
            for device_id, strategy in device_configs.items():
                name = self.get_device_display_name_for_serial(device_id)
                strategy_text = STRINGS.get("stop_waiting", "Stop and wait") if strategy else STRINGS.get("auto_supplement", "Auto recovery")
                lines.append(f"  {name}: {strategy_text}")
            device_config_text = "\n".join(lines)
        thresholds = config.get("thresholds", {})
        threshold_lines = []
        for platform, mapping in thresholds.items():
            item_lines = [
                f"    {STRINGS.get(f'threshold_{k}', k)} = {mapping.get(k)}"
                for k in mapping.keys()
            ]
            threshold_lines.append(f"  {platform}:\n" + "\n".join(item_lines))
        threshold_text = "\n".join(threshold_lines) if threshold_lines else "  -"
        info_text = (
            f"{STRINGS.get('config_info', 'Current Settings')}:\n\n"
            f"{STRINGS.get('wait_time_config', 'Wait Time Settings')}:\n{wait_times_str}\n\n"
            f"{STRINGS.get('energy_strategy_config', 'Energy Strategy')}: {energy_str}\n"
            f"{STRINGS.get('device_strategy_config', 'Per-device Energy Strategy')}:\n{device_config_text or '  -'}\n\n"
            f"{STRINGS.get('threshold_config', 'Threshold Settings')}:\n{threshold_text}"
        )
        self.config_info_label.setText(info_text)

    def apply_config_to_ui(self, config):
        self._loading_config = True
        try:
            for spin in self.wait_config.values():
                spin.blockSignals(True)
            self.energy_checkbox.blockSignals(True)
            for platform in self.threshold_config.values():
                for spin in platform.values():
                    spin.blockSignals(True)

            for key, spin in self.wait_config.items():
                if key in config.get("wait_times", {}):
                    spin.setValue(float(config["wait_times"][key]))
            self.energy_checkbox.setChecked(bool(config.get("energy_strategy", False)))

            thresholds = config.get("thresholds", {})
            for platform, mapping in self.threshold_config.items():
                for key, spin in mapping.items():
                    if key in thresholds.get(platform, {}):
                        spin.setValue(float(thresholds[platform][key]))

            self.device_strategy_map = deepcopy(config.get("device_configs", {})) if config else {}
        finally:
            for spin in self.wait_config.values():
                spin.blockSignals(False)
            self.energy_checkbox.blockSignals(False)
            for platform in self.threshold_config.values():
                for spin in platform.values():
                    spin.blockSignals(False)
            self._loading_config = False

        self.update_device_strategy_list()

        self.update_config_info_label(config)

    def load_saved_config(self):
        config = None
        if os.path.exists("bot_config.json"):
            try:
                with open("bot_config.json", "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception:
                config = None
        if config is None:
            config = self.default_config
        self.apply_config_to_ui(config)
        self.last_loaded_config = deepcopy(config)
        self.config_dirty = False
        self.update_save_button_state()
        self.set_config_editing_enabled(not self.is_running)

    def build_device_display_name(self, device):
        """憿舐內?瑁?憭模擬器 + serial"""
        if AUTOPVE_AVAILABLE and hasattr(autoPVE, "get_device_display_name"):
            try:
                return autoPVE.get_device_display_name(device)
            except Exception:
                pass
        serial = getattr(device, "serial", str(device))
        custom_name = None
        if hasattr(device, "shell"):
            settings_cmds = [
                "settings get global device_name",
                "settings get secure device_name",
                "settings get system device_name",
                "settings get secure bluetooth_name",
                "settings get system bluetooth_name"
            ]
            for cmd in settings_cmds:
                try:
                    value = device.shell(cmd).strip()
                except Exception:
                    value = ""
                if value and value.lower() not in {"null", "unknown", "generic"}:
                    custom_name = value
                    break
            if not custom_name:
                props = [
                    "ro.boot.qemu.avd_name",
                    "ro.kernel.qemu.avd_name",
                    "ro.boot.avd_name",
                    "persist.sys.display_name",
                    "persist.sys.device_name"
                ]
                for prop in props:
                    try:
                        value = device.shell(f"getprop {prop}").strip()
                    except Exception:
                        value = ""
                    if value and value.lower() not in {"unknown", "generic"}:
                        custom_name = value
                        break
        if custom_name:
            return f"{custom_name}({serial})"
        return serial

    def refresh_windows(self):
        """刷新PC窗口列表"""
        if self.is_running:
            self.append_log("[WARN] 執行中/暫停中不可刷新視窗")
            return
        if not AUTOPVE_AVAILABLE:
            self.append_log("[WARN] autoPVE 模組不可用，無法刷新視窗")
            return
        self.pc_windows_list.blockSignals(True)
        self.pc_windows_list.clear()
        self.pc_window_map.clear()
        try:
            self.append_log("[INFO] 正在刷新視窗...")
            windows = autoPVE.find_pc_game_windows()
            windows_list = list(windows.items())
            if windows_list:
                for i, (hwnd, title) in enumerate(windows_list):
                    display = f"[{i}] {title} (HWND: {hwnd})"
                    item = QListWidgetItem(display)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Unchecked)
                    self.pc_windows_list.addItem(item)
                    self.pc_window_map[display] = hwnd
                self.append_log(f"[OK] 成功檢測到 {len(windows_list)} 個PC視窗")
            else:
                self.append_log("[WARN] 找不到任何PC視窗")
        except Exception as e:
            self.append_log(f"[ERROR] 刷新視窗失敗: {e}")
        finally:
            self.pc_windows_list.blockSignals(False)
            self.update_start_stop_button()
            self.update_status_bar()
        
    def on_config_changed(self):
        """設定變更時更新存檔狀態"""
        if self.is_running or self._loading_config:
            return
        self.config_dirty = True
        self.update_save_button_state()
        self.update_status_bar()
        
    def save_config(self):
        config = {
            "wait_times": {k: v.value() for k, v in self.wait_config.items()},
            "energy_strategy": self.energy_checkbox.isChecked(),
            "device_configs": deepcopy(self.device_strategy_map) if hasattr(self, "device_strategy_map") else {},
            "thresholds": {
                platform: {k: spin.value() for k, spin in self.threshold_config[platform].items()}
                for platform in self.threshold_config
            }
        }
        try:
            with open("bot_config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            self.update_config_info_label(config)
            self.config_dirty = False
            self.last_loaded_config = deepcopy(config)
            self.update_save_button_state()
            self.append_log("[SUCCESS] Settings saved")
            self.update_status_bar()
        except Exception as e:
            self.append_log(f"[ERROR] Failed to save settings: {e}")
    
    def restore_defaults_and_save(self):
        self.apply_config_to_ui(self.default_config)
        self.config_dirty = True
        self.update_save_button_state()
        self.save_config()

    def reset_unsaved_changes(self):
        if self.last_loaded_config is not None:
            self.apply_config_to_ui(self.last_loaded_config)
        else:
            self.apply_config_to_ui(self.default_config)
        self.config_dirty = False
        self.update_save_button_state()
    def refresh_devices(self):
        """刷新設備列表 - 從ADB獲取實際設備"""
        if self.is_running:
            self.append_log("[WARN] 執行中/暫停中不可刷新設備")
            return
        self.device_list.blockSignals(True)
        try:
            self.append_log("[INFO] 正在刷新設備...")
            self.device_list.clear()
            self.device_map.clear()
            self.select_all_devices_checkbox.setChecked(False)

            from ppadb.client import Client as AdbClient
            client = AdbClient(host="127.0.0.1", port=5037)
            devices = client.devices()
            
            if devices:
                for device in devices:
                    # 問題 #5: 直接顯示 device.serial
                    display_name = self.build_device_display_name(device)
                    serial = getattr(device, "serial", None) or display_name
                    self.device_map[serial] = device
                    
                    # 問題 #6: 創建可勾選的項
                    item = QListWidgetItem(display_name)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Unchecked)
                    item.setData(Qt.UserRole, serial)
                    self.device_list.addItem(item)

                self.append_log(f"[OK] 成功檢測到 {len(devices)} 台設備")
                self.select_all_devices_checkbox.setEnabled(True)
            else:
                self.append_log("[WARN] 未檢測到任何設備，請確認ADB是否啟動")
                self.select_all_devices_checkbox.setEnabled(False)
        except ImportError:
             self.append_log("[ERROR] ppadb 模組未安裝，無法刷新設備")
             self.select_all_devices_checkbox.setEnabled(False)
        except Exception as e:
            self.append_log(f"[ERROR] 刷新設備失敗: {e}")
            # 如果ADB不可用，添加演示設備
            for i in range(1, 3):
                display_name = f"localhost:554{i}"
                item = QListWidgetItem(display_name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                item.setData(Qt.UserRole, display_name)
                self.device_list.addItem(item)
                self.device_map[display_name] = {"serial": display_name}
            self.append_log("[INFO] 使用本地演示設備")
            self.select_all_devices_checkbox.setEnabled(True)
        finally:
            self.device_list.blockSignals(False)
            self.update_device_strategy_list()
            self.update_start_stop_button()
            self.update_status_bar()
    
    def change_language(self):
        """切換語言"""
        global STRINGS
        lang_map = {
            0: "zh_TW",
            1: "zh_CN",
            2: "en"
        }
        self.current_language = lang_map[self.lang_combo.currentIndex()]
        STRINGS = load_localization_with_validation(self.current_language)
        # 確保所有 UI 元素都已創建後再更新
        if hasattr(self, 'tabs') and hasattr(self, 'wait_group'):
            self.update_all_ui_language()
        
    def update_all_ui_language(self):
        if hasattr(self, "threshold_group"):
            self.threshold_group.setTitle(STRINGS.get("threshold_config", "Threshold Settings"))
        """全面更新所有UI語言"""
        # 窗口標題
        self.setWindowTitle(STRINGS.get("app_title", "女王化身為無情的戰爭機器 小助手"))
        
        # 頂部語言欄
        self.lang_label.setText(STRINGS.get("language_label", "【語言】"))

        # 標籤文字
        self.tabs.setTabText(0, STRINGS.get("app_launch", "啟動"))
        self.tabs.setTabText(1, STRINGS.get("app_setting", "設定"))
        self.tabs.setTabText(2, STRINGS.get("app_console", "控制台"))
        self.tabs.setTabText(3, STRINGS.get("help_title", "說明"))
        
        # 啟動頁籤
        self.mode_group.setTitle(STRINGS.get("mode_selection", "選擇模式"))
        self.mode_combo.setItemText(0, STRINGS.get("mode_pc", "PC 模式"))
        self.mode_combo.setItemText(1, STRINGS.get("mode_emu", "模擬器模式"))
        self.device_group.setTitle(STRINGS.get("btn_select_device", "選擇設備"))
        self.select_all_devices_checkbox.setText(STRINGS.get("select_all", "全選"))
        self.pc_windows_group.setTitle(STRINGS.get("select_game_window", "選擇遊戲視窗"))
        
        self.refresh_devices_button.setText(STRINGS.get("btn_refresh_device", "刷新設備"))
        self.refresh_windows_button.setText(STRINGS.get("btn_refresh_window", "刷新視窗"))
        
        self.start_button.setText(STRINGS.get("btn_start", "啟動"))
        self.update_button_states() # 更新除錯和暫停按鈕的文字

        # 配置頁籤
        self.wait_group.setTitle(STRINGS.get("wait_time_config", "等待時間設定"))
        self.energy_group.setTitle(STRINGS.get("energy_strategy_config", "活力策略設定"))
        self.energy_checkbox.setText(STRINGS.get("stop_waiting", "停止並等待"))
        if hasattr(self, "energy_desc_label"):
            self.energy_desc_label.setText(f"{STRINGS.get('energy_description', '活力不足時')}:")
        if hasattr(self, "device_strategy_group"):
            self.device_strategy_group.setTitle(STRINGS.get("device_strategy_config", "Per-device Energy Strategy"))
        if hasattr(self, "device_strategy_hint"):
            hint_text = STRINGS.get(
                "device_strategy_hint",
                "Select devices in Launch tab to configure per-device strategy."
            )
            explain_text = STRINGS.get(
                "device_strategy_explain",
                "Checked = stop and wait; unchecked = auto recovery."
            )
            self.device_strategy_hint.setText(f"{hint_text}\n{explain_text}")
        if hasattr(self, "wait_labels"):
            for key, label in self.wait_labels.items():
                label_text = STRINGS.get(f"wait_{key}", key)
                label.setText(f"{label_text}")
        if hasattr(self, "threshold_labels"):
            for platform in self.threshold_labels:
                for key, label in self.threshold_labels[platform].items():
                    label_text = STRINGS.get(f"threshold_{key}", key)
                    label.setText(f"{label_text}")
        if hasattr(self, "restore_defaults_button"):
            self.restore_defaults_button.setText(STRINGS.get("btn_restore_defaults", "恢復預設並儲存"))
        if hasattr(self, "reset_changes_button"):
            self.reset_changes_button.setText(STRINGS.get("btn_reset_changes", "重置操作"))
        if hasattr(self, "wait_config"):
            current_config = {
                "wait_times": {k: v.value() for k, v in self.wait_config.items()},
                "energy_strategy": self.energy_checkbox.isChecked(),
                "device_configs": deepcopy(self.device_strategy_map) if hasattr(self, "device_strategy_map") else {},
                "thresholds": {
                    platform: {k: spin.value() for k, spin in self.threshold_config[platform].items()}
                    for platform in self.threshold_config
                }
            }
            self.update_config_info_label(current_config)
        
        # 控制台頁籤
        self.tabs.findChild(QLabel, "log_label").setText(STRINGS.get("error", "運行日誌"))
        help_text_content = (
            f"{STRINGS.get('help_shortcuts', '快捷鍵')}:\n"
            f"Ctrl+D - {STRINGS.get('help_debug', '開啟/關閉除錯模式')}\n"
            f"Ctrl+P - {STRINGS.get('help_pause', '暫停/繼續偵測')}\n"
            f"Ctrl+C - {STRINGS.get('help_stop', '停止腳本')}\n"
        )
        self.help_text.setText(help_text_content)
        self.clear_button.setText(STRINGS.get("btn_clear_log", "清空日誌"))
        
        # 說明頁籤
        features_text = (
            f"<b>{STRINGS.get('help_content', '功能簡介')}</b><br><br>"
            f"{STRINGS.get('help_features', '軟體支援兩種執行模式')}:<br>"
            f"• {STRINGS.get('help_pc_mode', 'PC 模式')}<br>"
            f"• {STRINGS.get('help_emu_mode', '模擬器模式')}<br><br>"
            f"<b>{STRINGS.get('help_principle_title', '運作原理')}</b><br>"
            f"{STRINGS.get('help_principle_desc', '透過畫面擷取與模板比對自動操作。')}<br><br>"
            f"<b>{STRINGS.get('help_steps_title', '詳細操作')}</b><br>"
            f"{STRINGS.get('help_steps_desc', '1. 選模式 2. 選設備/視窗 3. 設定參數 4. 啟動')}<br><br>"
            f"<b>{STRINGS.get('help_shortcuts', '快捷鍵')}</b><br>"
            f"• Ctrl+D: {STRINGS.get('help_debug', '切換除錯模式')}<br>"
            f"• Ctrl+P: {STRINGS.get('help_pause', '暫停或繼續')}<br>"
            f"• Ctrl+C: {STRINGS.get('help_stop', '停止程式')}<br><br>"
            f"<b>{STRINGS.get('help_config', '配置設定')}</b><br>"
            f"{STRINGS.get('help_config_desc', '在配置頁籤可以調整各項參數')}<br><br>"
            f"<b>{STRINGS.get('help_tips', '使用建議')}</b><br>"
            f"• {STRINGS.get('help_tip1', '首次執行時進行初始設定')}<br>"
            f"• {STRINGS.get('help_tip2', '如遇偵測失誤可微調門檻')}<br>"
            f"• {STRINGS.get('help_tip3', 'PC模式執行時保持視窗可見')}<br><br>"
            f"<b>{STRINGS.get('version_label', '版本')}</b>: v{APP_VERSION}"
        )
        self.help_content_label.setText(features_text)
        
        # 狀態欄與設定按鈕
        self.update_save_button_state()
        self.update_status_bar()
        self.setWindowTitle(f"{STRINGS.get('app_title', '女王化身為無情的戰爭機器 小助手')} v{APP_VERSION}")
    
    def collect_logs(self):
        """從日誌隊列收集並顯示日誌"""
        try:
            while not LOG_QUEUE.empty():
                msg = LOG_QUEUE.get_nowait()
                # 輸出到 GUI
                self.append_log(msg)
        except:
            pass
    
    def update_button_states(self):
        debug_state = STRINGS.get("debug_on", "ON") if self.is_debug else STRINGS.get("debug_off", "OFF")
        self.debug_button.setText(f"{STRINGS.get('btn_debug', 'Debug')} [{debug_state}]")

        pause_base = STRINGS.get("btn_pause", "Pause")
        if self.is_running and self.is_paused:
            pause_label = STRINGS.get("paused", "Paused")
            self.pause_button.setText(f"{pause_base} {pause_label}")
        else:
            self.pause_button.setText(pause_base)

        if self.is_running:
            self.pause_button.setEnabled(True)
            self.pause_button.setStyleSheet("background-color: #FF9800; color: white; padding: 12px; font-weight: bold; font-size: 12px;")
        else:
            self.pause_button.setEnabled(False)
            self.pause_button.setStyleSheet("background-color: #9E9E9E; color: white; padding: 12px; font-weight: bold; font-size: 12px;")

        self.update_start_stop_button()
        
    @pyqtSlot(str)
    def append_log(self, message):
        """添加日誌"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        self.log_text.moveCursor(QTextCursor.End)
        
    def update_status(self, text, color):
        del text, color
        self.update_status_bar()

    def setup_shortcuts(self):
        self.shortcut_stop = QShortcut(QKeySequence("Ctrl+C"), self)
        self.shortcut_stop.setContext(Qt.ApplicationShortcut)
        self.shortcut_stop.activated.connect(self.handle_stop_shortcut)

    def handle_stop_shortcut(self):
        if self.is_running:
            self.stop_bot()
        else:
            self.close()

    def closeEvent(self, event):
        """處理窗口關閉事件"""
        self.stop_bot()
        event.accept()

def main():
    """主入點"""
    global STRINGS
    
    # 嘗試導入 autoPVE 並設置日誌隊列
    try:
        import autoPVE as bot_engine
        bot_engine.LOG_QUEUE = LOG_QUEUE
        bot_engine.LOG_QUEUE = LOG_QUEUE  # 共享日誌隊列
    except:
        pass
    
    app = QApplication(sys.argv)
    # Allow Ctrl+C to close the GUI cleanly in console mode
    def handle_sigint(*args):
        app.quit()
    signal.signal(signal.SIGINT, handle_sigint)
    sigint_timer = QTimer()
    sigint_timer.start(200)
    sigint_timer.timeout.connect(lambda: None)
    app._sigint_timer = sigint_timer
    STRINGS = load_localization("zh_TW")
    
    window = MainGUI()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
