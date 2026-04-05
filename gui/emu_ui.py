"""
gui/emu_ui.py
EmuUIMixin - EMU 模式 UI 建構 mixin
包含 init_ui、語言切換、各頁籤建構、欄位說明工具提示
"""

import os

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTabWidget,
    QGroupBox, QFormLayout, QListWidget, QListWidgetItem, QTextEdit,
    QCheckBox, QDoubleSpinBox, QGridLayout, QComboBox, QScrollArea,
    QShortcut, QLineEdit, QSpinBox, QDialog, QToolTip, QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer, QEvent
from PyQt5.QtGui import QFont as _QFont, QKeySequence, QCursor

from i18n import t

from gui.shared import resource_path, APP_VERSION, build_template_tooltip_html


class EmuUIMixin:
    """EMU 模式 UI mixin：建構各頁籤、語言切換、工具提示"""

    # ── 模板預覽 ───────────────────────────────────────────────
    def _bind_template_preview(self, widget, template_key):
        widget.setContextMenuPolicy(Qt.CustomContextMenu)
        widget.customContextMenuRequested.connect(
            lambda _pos, k=template_key: self._show_template_preview_dialog(k)
        )

    def _show_template_preview_dialog(self, template_key):
        filename = f"{template_key}.png"
        image_path = resource_path(os.path.join("templates", filename))
        dlg = QDialog(self)
        dlg.setWindowTitle(f"模板預覽 - {filename}")
        layout = QVBoxLayout(dlg)
        info = QLabel(filename)
        layout.addWidget(info)

        preview = QLabel()
        preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        if os.path.exists(image_path):
            image_src = image_path.replace("\\", "/")
            preview.setText(f"<img src='{image_src}' width='520'>")
        else:
            preview.setText(f"找不到模板圖片: {image_path}")
        layout.addWidget(preview)

        close_btn = QPushButton("關閉")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)
        dlg.exec_()

    # ── 初始化 UI ──────────────────────────────────────────────
    def init_ui(self):
        """初始化 UI"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout()
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
        self.status_label.setFont(_QFont("Arial", 10, _QFont.Bold))
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.start_btn = QPushButton(t("btn_start", "啟動"))
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-weight: bold;")
        self.start_btn.clicked.connect(self.on_start_stop)
        self.start_btn.setEnabled(False)
        status_layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton(t("btn_pause", "暫停"))
        self.pause_btn.setStyleSheet("background-color: #9E9E9E; color: #CCCCCC; padding: 10px; font-weight: bold;")
        self.pause_btn.clicked.connect(self.on_pause)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText(t("btn_pause", "暫停"))
        status_layout.addWidget(self.pause_btn)

        self.debug_btn = QPushButton(t("btn_debug", "除錯模式"))
        self.debug_btn.setStyleSheet("background-color: #2196F3; color: white; padding: 10px; font-weight: bold;")
        self.debug_btn.clicked.connect(self.on_debug)
        status_layout.addWidget(self.debug_btn)

        main_layout.addLayout(status_layout)

        central.setLayout(main_layout)

        # === 快捷鍵 ===
        self.shortcut_start_stop = QShortcut(QKeySequence("Ctrl+C"), self, self._shortcut_start_stop)
        self.shortcut_pause = QShortcut(QKeySequence("Ctrl+P"), self, self._shortcut_pause)
        self.shortcut_debug = QShortcut(QKeySequence("Ctrl+D"), self, self._shortcut_debug)
        self.shortcut_start_stop.setAutoRepeat(False)
        self.shortcut_pause.setAutoRepeat(False)
        self.shortcut_debug.setAutoRepeat(False)

        # === 定時器 ===
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.collect_logs)
        self.log_timer.start(200)

        self._apply_input_ux()

    def on_language_changed(self, index):
        """語言變更事件"""
        from i18n import set_language
        lang_map = {0: "zh_TW", 1: "zh_CN", 2: "en"}
        set_language(lang_map.get(index, "zh_TW"))
        self.update_ui_texts()
        self.append_log("[INFO] " + t("config_loaded", "語言已切換"))

    def update_ui_texts(self):
        """更新所有 UI 文字為當前語言"""
        self.setWindowTitle(t("app_title", "女王的飄流小助手") + f" - EMU v{APP_VERSION}")

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
            self.pause_btn.setText(t("btn_resume", "繼續執行"))

        if not self.is_debug:
            self.debug_btn.setText(t("btn_debug", "除錯模式"))
        else:
            self.debug_btn.setText(t("debug_mode", "除錯模式") + " [ON]")

        # 設定頁
        self.config_subtabs.setTabText(0, t("settings_auto_battle_tab", "自動玩家對戰"))
        self.config_subtabs.setTabText(1, t("settings_disconnect_tab", "斷線重連"))
        self.config_group_left.setTitle(t("wait_time_config", "等待時間設定") + " (s)")
        self.config_group_right.setTitle(t("threshold_config", "辨識閾值設定"))
        self.reconnect_wait_group.setTitle(t("reconnect_wait_config", "等待時間設定") + " (s)")
        self.disconnect_threshold_group.setTitle(t("disconnect_threshold_config", "辨識閾值設定"))
        self.auto_feature_wait_group.setTitle(t("wait_time_config", "等待時間設定") + " (s)")
        self.disconnect_threshold_section_a_group.setTitle(t("disconnect_threshold_section_a", "斷線提示與返回"))
        self.disconnect_threshold_section_b_group.setTitle(t("disconnect_threshold_section_b", "登入流程"))
        self.disconnect_threshold_section_c_group.setTitle(t("disconnect_threshold_section_c", "遊戲公告與彈窗"))
        self.disconnect_threshold_section_d_group.setTitle(t("disconnect_threshold_section_d", "辨識閾值設定"))
        self.config_subtabs.setTabText(2, t("settings_auto_features_tab", "自動開啟功能"))
        self.auto_enable_features_check.setText(t("reconnect_auto_features_enable", "啟用自動開啟功能"))
        self.auto_enable_wander_check.setText(t("reconnect_auto_wander_enable", "自動開啟徘徊"))
        self.auto_enable_ai_check.setText(t("reconnect_auto_ai_enable", "自動開啟 AI"))

        disconnect_threshold_i18n_keys = {
            "disconnect_hint": "threshold_disconnect_hint",
            "btn_reconnect": "threshold_btn_reconnect",
            "btn_back_to_login": "threshold_btn_back_to_login",
            "login_from_other_place": "threshold_login_from_other_place",
            "multi_login": "threshold_multi_login",
            "custom_login": "threshold_custom_login",
            "btn_login_account": "threshold_btn_login_account",
            "select_server": "threshold_select_server",
            "select_character": "threshold_select_character",
            "login_game_button": "threshold_login_game_button",
            "pop_gift_box": "threshold_pop_gift_box",
            "start_game_announcement": "threshold_start_game_announcement",
            "announcement": "threshold_announcement",
            "update_resource": "threshold_update_resource",
            "dont_ask_today": "threshold_dont_ask_today",
            "btn_cross": "threshold_btn_cross",
            "btn_power_saving": "threshold_btn_power_saving",
            "btn_wander_on": "threshold_btn_wander_on",
            "btn_wander_off": "threshold_btn_wander_off",
            "btn_ai": "threshold_btn_ai",
            "btn_ai_off_in_battle": "threshold_btn_ai_off_in_battle",
        }
        for key, i18n_key in disconnect_threshold_i18n_keys.items():
            if key in self.disconnect_threshold_labels:
                self.disconnect_threshold_labels[key].setText(t(i18n_key, key) + ":")

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
            "battle_title": "threshold_title",
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
        self.auto_battle_enable_check.setText(t("auto_battle_enable", "啟用自動玩家對戰"))
        self.energy_check.setText(t("stop_waiting", "低活力時停止（不補充）"))
        self.disconnect_enable_check.setText(t("disconnect_enable", "啟用斷線重連"))
        self.max_reconnect_unlimited_check.setText(t("reconnect_unlimited", "無限重試"))

        self.device_energy_group.setTitle(t("device_strategy_config", "每台設備活力策略"))
        self.device_energy_info.setText(
            t("device_strategy_hint", "先在啟動頁選擇設備，才可設定個別策略。")
            + "\n"
            + t("device_strategy_explain", "勾選＝停止等待（不補充）；未勾選＝自動補充。")
        )
        self.device_auto_feature_group.setTitle(t("device_auto_feature_config", "每台設備自動開啟功能"))
        self.device_auto_feature_info.setText(t("device_auto_feature_hint", "先在啟動頁選擇設備，才可設定個別自動開啟功能。"))
        self.emu_path_group.setTitle(t("ldplayer_install_path", "LDPlayer 安裝路徑設定"))
        self.emu_package_group.setTitle(t("disconnect_emu_package_label", "EMU 套件名稱"))
        self.emu_package_label.setText(t("disconnect_emu_package_label", "EMU 套件名稱") + ":")
        for btn in self.browse_buttons.values():
            btn.setText(t("btn_browse", "瀏覽"))
        self.update_device_energy_settings()
        self.update_device_auto_feature_settings()

        self.save_btn.setText(t("config_change", "儲存設定"))
        self.reset_btn.setText(t("btn_reset_changes", "重置變更"))
        self.restore_btn.setText(t("btn_restore_defaults", "恢復預設"))
        self.launch_save_btn.setText(t("config_change", "儲存設定"))
        self.launch_reset_btn.setText(t("btn_reset_changes", "重置變更"))
        self.launch_restore_btn.setText(t("btn_restore_defaults", "恢復預設"))

        if hasattr(self, "max_reconnect_label"):
            self.max_reconnect_label.setText(t("disconnect_max_attempts_label", "最大重連次數") + ":")
        if hasattr(self, "screen_hash_diff_label"):
            self.screen_hash_diff_label.setText(t("screen_hash_diff_threshold", "同畫面辨識差異閾值") + ":")

        _form_label_map = [
            (self.reconnect_wait_left_form, self.same_screen_timeout_spin, "disconnect_same_screen_timeout_label", "同畫面逾時"),
            (self.reconnect_wait_right_form, self.pc_launch_wait_timeout_spin, "pc_launch_wait_timeout", "重啟等待時間"),
            (self.reconnect_wait_right_form, self.screen_hash_interval_spin, "screen_hash_interval", "辨識畫面間隔"),
            (self.reconnect_wait_left_form, self.action_cooldown_spin, "action_cooldown", "點擊等待時間"),
            (self.reconnect_wait_right_form, self.check_game_open_interval_spin, "check_game_open_interval_minutes", "遊戲開啟檢查間隔(分)"),
            (self.reconnect_wait_left_form, self.login_timeout_spin, "login_timeout", "登入逾時"),
            (self.reconnect_wait_left_form, self.post_login_timeout_spin, "post_login_timeout", "登入後逾時"),
        ]
        for form, widget, i18n_key, fallback in _form_label_map:
            label = form.labelForField(widget)
            if label:
                label.setText(t(i18n_key, fallback) + ":")

        if hasattr(self, "auto_feature_action_cooldown_label"):
            self.auto_feature_action_cooldown_label.setText(t("auto_feature_action_cooldown", "點擊等待時間") + ":")
        if hasattr(self, "auto_feature_scan_interval_label"):
            self.auto_feature_scan_interval_label.setText(t("auto_feature_scan_interval", "辨識畫面間隔") + ":")
        if hasattr(self, "in_game_confirm_timeout_label"):
            self.in_game_confirm_timeout_label.setText(t("in_game_confirm_timeout", "遊戲內確認逾時") + ":")

        self._apply_field_help_tooltips()

        # 控制台
        self.log_group.setTitle(t("error", "輸出日誌"))
        self.log_filter_level_label.setText(t("log_filter_level", "層級篩選") + ":")
        self.log_filter_level_combo.setItemText(0, t("log_level_all", "全部"))
        self.log_filter_keyword_label.setText(t("log_filter_keyword", "關鍵字") + ":")
        self.log_filter_input.setPlaceholderText(t("log_filter_keyword_placeholder", "輸入關鍵字即時過濾"))
        self.log_filter_clear_btn.setText(t("log_filter_clear", "清除篩選"))
        self.clear_log_btn.setText(t("btn_clear_log", "清空日誌"))

        self._update_help_text()

        self._label_base_texts = {}
        self._checkbox_base_texts = {}
        self.update_current_config_display()

        if not self.is_running:
            self.status_label.setText(t("status_ready", "準備就緒"))
        elif self.is_paused:
            self.status_label.setText(t("paused", "已暫停"))
        else:
            self.status_label.setText(t("resumed", "執行中"))

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and isinstance(obj, (QSpinBox, QDoubleSpinBox, QComboBox)):
            if not obj.hasFocus():
                return True
        return super().eventFilter(obj, event)

    def _apply_input_ux(self):
        """避免誤滑造成數值變動，並降低捲動區滾動步進。"""
        for w in self.findChildren((QSpinBox, QDoubleSpinBox, QComboBox)):
            w.setFocusPolicy(Qt.StrongFocus)
            w.installEventFilter(self)
            if isinstance(w, (QSpinBox, QDoubleSpinBox)):
                w.setKeyboardTracking(False)

        for area in self.findChildren(QScrollArea):
            area.verticalScrollBar().setSingleStep(12)

    def _bind_field_help_context(self, widget, help_text):
        """右鍵顯示欄位說明（非閾值區塊）。"""
        if not widget or not help_text:
            return
        widget.setContextMenuPolicy(Qt.CustomContextMenu)
        widget.customContextMenuRequested.connect(
            lambda _pos, w=widget, txt=help_text: QToolTip.showText(QCursor.pos(), txt, w)
        )

    def _apply_field_help_tooltips(self):
        """為可調欄位套用 hover/右鍵說明（閾值區塊除外）。"""
        field_help = {
            "scan_interval": t("help_field_wait_scan_interval", "每次畫面偵測的間隔秒數。"),
            "after_click": t("help_field_wait_after_click", "每次點擊後等待畫面穩定的時間。"),
            "pop_window": t("help_field_wait_pop_window", "等待彈窗出現或切換完成的時間。"),
            "battle_unlock": t("help_field_wait_battle_unlock", "判斷戰鬥結束前的緩衝等待時間。"),
            "join_confirm": t("help_field_wait_join_confirm", "按下加入後等待確認的時間。"),
            "wait_battle_check": t("help_field_wait_battle_check", "等待進入戰鬥的最長檢查時間。"),
        }
        for key, tip in field_help.items():
            label = self.wait_labels.get(key)
            spinner = self.wait_spinners.get(key)
            if label:
                label.setToolTip(tip)
                self._bind_field_help_context(label, tip)
            if spinner:
                spinner.setToolTip(tip)
                self._bind_field_help_context(spinner, tip)

        common_pairs = [
            (self.auto_battle_enable_check, t("help_field_auto_battle_enable", "開啟後才會執行自動玩家對戰主流程。")),
            (self.energy_check, t("help_field_energy_strategy", "勾選後偵測到低活力會停止，不自動補充。")),
            (self.disconnect_enable_check, t("help_field_disconnect_enable", "開啟後才會啟用斷線偵測與重連流程。")),
            (self.same_screen_timeout_spin, t("help_field_same_screen_timeout", "同畫面持續超過此秒數時，判定可能卡住/斷線。")),
            (self.max_reconnect_attempts_spin, t("help_field_max_reconnect_attempts", "重連流程最多嘗試次數。")),
            (self.max_reconnect_unlimited_check, t("help_field_unlimited_retry", "勾選後重連次數不受上限限制。")),
            (self.pc_launch_wait_timeout_spin, t("help_field_restart_wait_timeout", "重啟後等待遊戲建立與穩定的秒數。")),
            (self.emu_package_input, t("help_field_emu_package_name", "要重啟的 EMU 遊戲套件名稱。")),
            (self.screen_hash_diff_threshold_spin, t("help_field_screen_hash_diff", "畫面差異低於此值會視為同畫面。")),
            (self.screen_hash_interval_spin, t("help_field_screen_hash_interval", "同畫面檢測的取樣間隔秒數。")),
            (self.action_cooldown_spin, t("help_field_action_cooldown", "重連流程每次操作之間的等待時間。")),
            (self.auto_feature_action_cooldown_spin, t("help_field_auto_feature_action_cooldown", "自動開啟功能每次操作之間的等待時間。")),
            (self.auto_feature_scan_interval_spin, t("help_field_auto_feature_scan_interval", "自動開啟功能每次辨識的間隔秒數。")),
            (self.check_game_open_interval_spin, t("help_field_game_open_check_interval", "每隔幾分鐘檢查一次遊戲是否仍在開啟；若未開啟則進入重開遊戲流程。")),
            (self.login_timeout_spin, t("help_field_login_timeout", "登入流程可等待的最長秒數。")),
            (self.post_login_timeout_spin, t("help_field_post_login_timeout", "登入後到進入遊戲前的最長等待秒數。")),
            (self.in_game_confirm_timeout_spin, t("help_field_in_game_confirm_timeout", "進入遊戲後確認流程可等待的最長秒數。")),
            (self.restart_game_enable_check, t("help_field_flow_a_enable", "流程 A：重開遊戲。")),
            (self.login_game_enable_check, t("help_field_flow_b_enable", "流程 B：登入遊戲。")),
            (self.auto_enable_features_check, t("help_field_auto_features_enable", "開啟後會在遊戲內自動維持功能狀態。")),
            (self.auto_enable_wander_check, t("help_field_auto_wander", "重連完成後自動開啟徘徊。")),
            (self.auto_enable_ai_check, t("help_field_auto_ai", "重連完成後自動開啟 AI。")),
        ]
        for widget, tip in common_pairs:
            if widget:
                widget.setToolTip(tip)
                self._bind_field_help_context(widget, tip)

        form_tips = [
            (self.reconnect_wait_left_form, self.same_screen_timeout_spin, t("help_field_same_screen_timeout", "同畫面持續超過此秒數時，判定可能卡住/斷線。")),
            (self.reconnect_wait_right_form, self.pc_launch_wait_timeout_spin, t("help_field_restart_wait_timeout", "重啟後等待遊戲建立與穩定的秒數。")),
            (self.reconnect_wait_right_form, self.screen_hash_interval_spin, t("help_field_screen_hash_interval", "同畫面檢測的取樣間隔秒數。")),
            (self.reconnect_wait_left_form, self.action_cooldown_spin, t("help_field_action_cooldown", "重連流程每次操作之間的等待時間。")),
            (self.reconnect_wait_right_form, self.check_game_open_interval_spin, t("help_field_game_open_check_interval", "每隔幾分鐘檢查一次遊戲是否仍在開啟；若未開啟則進入重開遊戲流程。")),
            (self.reconnect_wait_left_form, self.login_timeout_spin, t("help_field_login_timeout", "登入流程可等待的最長秒數。")),
            (self.reconnect_wait_left_form, self.post_login_timeout_spin, t("help_field_post_login_timeout", "登入後到進入遊戲前的最長等待秒數。")),
        ]
        for form, field, tip in form_tips:
            label = form.labelForField(field)
            if label:
                label.setToolTip(tip)
                self._bind_field_help_context(label, tip)

        auto_feature_label_tips = [
            ("auto_feature_action_cooldown_label", t("help_field_auto_feature_action_cooldown", "自動開啟功能每次操作之間的等待時間。")),
            ("auto_feature_scan_interval_label", t("help_field_auto_feature_scan_interval", "自動開啟功能每次辨識的間隔秒數。")),
            ("in_game_confirm_timeout_label", t("help_field_in_game_confirm_timeout", "進入遊戲後確認流程可等待的最長秒數。")),
        ]
        for attr_name, tip in auto_feature_label_tips:
            label = getattr(self, attr_name, None)
            if label:
                label.setToolTip(tip)
                self._bind_field_help_context(label, tip)

        if hasattr(self, "max_reconnect_label"):
            max_attempts_tip = t("help_field_max_reconnect_attempts", "重連流程最多嘗試次數。")
            self.max_reconnect_label.setToolTip(max_attempts_tip)
            self._bind_field_help_context(self.max_reconnect_label, max_attempts_tip)
        if hasattr(self, "screen_hash_diff_label"):
            diff_tip = t("help_field_screen_hash_diff", "畫面差異低於此值會視為同畫面。")
            self.screen_hash_diff_label.setToolTip(diff_tip)
            self._bind_field_help_context(self.screen_hash_diff_label, diff_tip)

    # ── 啟動頁 ─────────────────────────────────────────────────
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

        # LDPlayer 安裝路徑
        self.emu_path_group = QGroupBox(t("ldplayer_install_path", "LDPlayer 安裝路徑設定"))
        emu_path_layout = QFormLayout()
        self.emulator_path_inputs = {}
        self.browse_buttons = {}
        path_layout = QHBoxLayout()
        path_input = QLineEdit()
        path_input.setPlaceholderText(r"D:\LDPlayer")
        path_input.textChanged.connect(self.on_config_changed)
        self.emulator_path_inputs["ldplayer"] = path_input
        path_layout.addWidget(path_input)

        browse_btn = QPushButton(t("btn_browse", "瀏覽"))
        browse_btn.setMaximumWidth(60)
        browse_btn.clicked.connect(lambda checked: self.browse_emulator_path("ldplayer"))
        self.browse_buttons["ldplayer"] = browse_btn
        path_layout.addWidget(browse_btn)

        ld_help = t(
            "help_field_ldplayer_install_path",
            "設定 LDPlayer 安裝目錄，供偵測與重啟流程使用。執行中不可變更。",
        )
        ld_label = QLabel("LDPlayer:")
        ld_label.setToolTip(ld_help)
        self._bind_field_help_context(ld_label, ld_help)
        path_input.setToolTip(ld_help)
        self._bind_field_help_context(path_input, ld_help)
        browse_btn.setToolTip(ld_help)
        self._bind_field_help_context(browse_btn, ld_help)
        self.emu_path_group.setToolTip(ld_help)
        self._bind_field_help_context(self.emu_path_group, ld_help)

        emu_path_layout.addRow(ld_label, path_layout)
        self.emu_path_group.setLayout(emu_path_layout)
        layout.addWidget(self.emu_path_group)

        # EMU 套件名稱
        self.emu_package_group = QGroupBox(t("disconnect_emu_package_label", "EMU 套件名稱"))
        emu_package_layout = QFormLayout()
        self.emu_package_input = QLineEdit()
        self.emu_package_input.setPlaceholderText("com.chinesegamer.wlnmy")
        self.emu_package_input.setText(self.current_config.get("disconnect", {}).get("emu_package_name", ""))
        self.emu_package_input.textChanged.connect(self.on_config_changed)

        emu_pkg_help = t("help_field_emu_package_name", "要重啟的 EMU 遊戲套件名稱。")
        emu_pkg_label = QLabel(t("disconnect_emu_package_label", "EMU 套件名稱") + ":")
        self.emu_package_label = emu_pkg_label
        emu_pkg_label.setToolTip(emu_pkg_help)
        self._bind_field_help_context(emu_pkg_label, emu_pkg_help)
        self.emu_package_input.setToolTip(emu_pkg_help)
        self._bind_field_help_context(self.emu_package_input, emu_pkg_help)
        self.emu_package_group.setToolTip(emu_pkg_help)
        self._bind_field_help_context(self.emu_package_group, emu_pkg_help)

        emu_package_layout.addRow(emu_pkg_label, self.emu_package_input)
        self.emu_package_group.setLayout(emu_package_layout)
        layout.addWidget(self.emu_package_group)

        launch_btn_layout = QHBoxLayout()
        self.launch_save_btn = QPushButton(t("config_change", "保存設定"))
        self.launch_save_btn.clicked.connect(self.save_config)
        self.launch_save_btn.setEnabled(False)
        launch_btn_layout.addWidget(self.launch_save_btn)

        self.launch_reset_btn = QPushButton(t("btn_reset_changes", "重置變更"))
        self.launch_reset_btn.clicked.connect(self.reset_changes)
        self.launch_reset_btn.setEnabled(False)
        launch_btn_layout.addWidget(self.launch_reset_btn)

        self.launch_restore_btn = QPushButton(t("btn_restore_defaults", "恢復預設"))
        self.launch_restore_btn.clicked.connect(self.restore_defaults)
        launch_btn_layout.addWidget(self.launch_restore_btn)
        layout.addLayout(launch_btn_layout)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    # ── 設定頁 ─────────────────────────────────────────────────
    def create_config_tab(self):
        """設定標籤（自動玩家對戰 / 斷線重連分頁）"""
        widget = QWidget()
        layout = QVBoxLayout()

        self.config_subtabs = QTabWidget()

        # =============================================
        # === 自動玩家對戰分頁 ===
        # =============================================
        auto_tab = QWidget()
        auto_layout = QVBoxLayout()

        self.auto_battle_enable_check = QCheckBox(t("auto_battle_enable", "啟用自動玩家對戰"))
        self.auto_battle_enable_check.setChecked(self.current_config.get("auto_battle_enabled", True))
        self.auto_battle_enable_check.setStyleSheet(
            "font-weight: bold; font-size: 11pt; padding: 4px;"
            "background: #E8F5E9; border-radius: 4px;"
        )
        self.auto_battle_enable_check.stateChanged.connect(self._on_auto_battle_enable_changed)
        auto_layout.addWidget(self.auto_battle_enable_check)

        auto_scroll = QScrollArea()
        auto_scroll.setWidgetResizable(True)
        auto_scroll_widget = QWidget()
        auto_scroll_layout = QVBoxLayout(auto_scroll_widget)

        auto_columns_layout = QHBoxLayout()

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

        self.energy_label = QLabel(t("energy_strategy_config", "活力策略") + ":")
        self.energy_check = QCheckBox(t("stop_waiting", "低活力時停止（不補充）"))
        self.energy_check.setChecked(self.current_config["energy_strategy"])
        self.energy_check.stateChanged.connect(self.on_config_changed)
        left_form.addRow(self.energy_label, self.energy_check)

        self.config_group_left.setLayout(left_form)
        left_column.addWidget(self.config_group_left)
        left_column.addStretch()
        auto_columns_layout.addLayout(left_column)

        right_column = QVBoxLayout()
        self.config_group_right = QGroupBox(t("threshold_config", "辨識閾值設定"))
        right_form = QFormLayout()

        self.threshold_spinners = {}
        self.threshold_labels = {}
        default_thresholds = self.default_config.get("thresholds", {}).get("EMU", {})
        threshold_names = {
            "battle_title": ("threshold_title", "標題辨識閾值"),
            "btn_add": ("threshold_btn_add", "加號按鈕閾值"),
            "btn_confirm": ("threshold_btn_confirm", "確認按鈕閾值"),
            "btn_join": ("threshold_btn_join", "搜尋對手按鈕閾值"),
            "in_battle": ("threshold_in_battle", "戰鬥中閾值"),
            "energy_low": ("threshold_energy_low", "低活力閾值"),
            "energy_9": ("threshold_energy_9", "滿活力閾值")
        }

        for key, (i18n_key, fallback) in threshold_names.items():
            spinner = QDoubleSpinBox()
            spinner.setRange(0.01, 1.0)
            spinner.setDecimals(2)
            spinner.setSingleStep(0.01)
            spinner.setValue(self.current_config["thresholds_emu"].get(key, default_thresholds.get(key, 0.70)))
            spinner.valueChanged.connect(self.on_config_changed)
            tooltip_html = build_template_tooltip_html(key)
            spinner.setToolTip(tooltip_html)
            self._bind_template_preview(spinner, key)
            self.threshold_spinners[key] = spinner
            label = QLabel(t(i18n_key, fallback) + ":")
            label.setToolTip(tooltip_html)
            self._bind_template_preview(label, key)
            self.threshold_labels[key] = label
            right_form.addRow(label, spinner)

        self.config_group_right.setLayout(right_form)
        right_column.addWidget(self.config_group_right)
        right_column.addStretch()
        auto_columns_layout.addLayout(right_column)

        auto_scroll_layout.addLayout(auto_columns_layout)

        # 每台設備活力策略
        bottom_columns = QHBoxLayout()

        self.device_energy_group = QGroupBox(t("device_strategy_config", "每台設備活力策略"))
        device_energy_layout = QVBoxLayout()
        self.device_energy_info = QLabel(
            t("device_strategy_hint", "先在啟動頁選擇設備，才可設定個別策略。")
            + "\n"
            + t("device_strategy_explain", "勾選＝停止等待（不補充）；未勾選＝自動補充。")
        )
        self.device_energy_info.setStyleSheet("color: #666; font-size: 9pt;")
        self.device_energy_info.setWordWrap(True)
        device_energy_layout.addWidget(self.device_energy_info)
        self.device_energy_checks = {}
        self.device_energy_container = QWidget()
        self.device_energy_container_layout = QVBoxLayout(self.device_energy_container)
        device_energy_layout.addWidget(self.device_energy_container)
        self.device_energy_group.setLayout(device_energy_layout)
        bottom_columns.addWidget(self.device_energy_group)

        auto_scroll_layout.addLayout(bottom_columns)

        auto_scroll_layout.addStretch()
        auto_scroll.setWidget(auto_scroll_widget)
        auto_layout.addWidget(auto_scroll)
        auto_tab.setLayout(auto_layout)

        # =============================================
        # === 斷線重連分頁 ===
        # =============================================
        reconnect_tab = QWidget()
        reconnect_layout = QVBoxLayout()

        self.disconnect_enable_check = QCheckBox(t("disconnect_enable", "啟用斷線重連"))
        self.disconnect_enable_check.setStyleSheet(
            "font-weight: bold; font-size: 11pt; padding: 4px;"
            "background: #E3F2FD; border-radius: 4px;"
        )
        disconnect_cfg = self.current_config.get("disconnect", {})
        self.disconnect_enable_check.setChecked(disconnect_cfg.get("enabled", True))
        self.disconnect_enable_check.stateChanged.connect(self._on_disconnect_enable_changed)
        reconnect_layout.addWidget(self.disconnect_enable_check)

        reconnect_scroll = QScrollArea()
        reconnect_scroll.setWidgetResizable(True)
        reconnect_scroll_widget = QWidget()
        reconnect_scroll_layout = QVBoxLayout(reconnect_scroll_widget)
        reconnect_scroll_layout.setContentsMargins(0, 0, 0, 0)
        reconnect_scroll_layout.setSpacing(8)

        self.same_screen_timeout_spin = QDoubleSpinBox()
        self.same_screen_timeout_spin.setRange(5.0, 600.0)
        self.same_screen_timeout_spin.setSingleStep(1.0)
        self.same_screen_timeout_spin.setValue(disconnect_cfg.get("same_screen_timeout", 45.0))
        self.same_screen_timeout_spin.valueChanged.connect(self.on_config_changed)

        max_attempts_layout = QHBoxLayout()
        self.max_reconnect_attempts_spin = QSpinBox()
        self.max_reconnect_attempts_spin.setRange(1, 99)
        saved_attempts = disconnect_cfg.get("max_reconnect_attempts", 5)
        self.max_reconnect_attempts_spin.setValue(max(1, saved_attempts) if saved_attempts != 0 else 5)
        self.max_reconnect_attempts_spin.valueChanged.connect(self.on_config_changed)
        max_attempts_layout.addWidget(self.max_reconnect_attempts_spin)
        self.max_reconnect_unlimited_check = QCheckBox(t("reconnect_unlimited", "無限重試"))
        self.max_reconnect_unlimited_check.setChecked(saved_attempts == 0)
        self.max_reconnect_unlimited_check.stateChanged.connect(self._on_unlimited_changed)
        max_attempts_layout.addWidget(self.max_reconnect_unlimited_check)
        self._max_attempts_layout = max_attempts_layout

        self.pc_launch_wait_timeout_spin = QDoubleSpinBox()
        self.pc_launch_wait_timeout_spin.setRange(5.0, 300.0)
        self.pc_launch_wait_timeout_spin.setDecimals(0)
        self.pc_launch_wait_timeout_spin.setSingleStep(5.0)
        self.pc_launch_wait_timeout_spin.setValue(disconnect_cfg.get("pc_launch_wait_timeout", 25.0))
        self.pc_launch_wait_timeout_spin.valueChanged.connect(self.on_config_changed)

        self.screen_hash_diff_threshold_spin = QDoubleSpinBox()
        self.screen_hash_diff_threshold_spin.setRange(0.1, 100.0)
        self.screen_hash_diff_threshold_spin.setDecimals(1)
        self.screen_hash_diff_threshold_spin.setSingleStep(0.5)
        self.screen_hash_diff_threshold_spin.setValue(disconnect_cfg.get("screen_hash_diff_threshold", 5.0))
        self.screen_hash_diff_threshold_spin.valueChanged.connect(self.on_config_changed)

        max_diff_row = QWidget()
        max_diff_layout = QHBoxLayout(max_diff_row)
        max_diff_layout.setContentsMargins(0, 0, 0, 0)
        max_diff_layout.setSpacing(12)

        max_attempts_widget = QWidget()
        max_attempts_row_layout = QHBoxLayout(max_attempts_widget)
        max_attempts_row_layout.setContentsMargins(12, 0, 0, 0)
        max_attempts_row_layout.setSpacing(6)
        self.max_reconnect_label = QLabel(t("disconnect_max_attempts_label", "最大重連次數") + ":")
        max_attempts_row_layout.addWidget(self.max_reconnect_label)
        max_attempts_row_layout.addLayout(max_attempts_layout)
        max_attempts_row_layout.addStretch()

        max_diff_layout.addWidget(max_attempts_widget, 1)
        max_diff_layout.addStretch()
        reconnect_scroll_layout.addWidget(max_diff_row)

        self.screen_hash_interval_spin = QDoubleSpinBox()
        self.screen_hash_interval_spin.setRange(0.1, 60.0)
        self.screen_hash_interval_spin.setDecimals(1)
        self.screen_hash_interval_spin.setSingleStep(0.1)
        self.screen_hash_interval_spin.setValue(disconnect_cfg.get("screen_hash_interval", 1.0))
        self.screen_hash_interval_spin.valueChanged.connect(self.on_config_changed)

        # 等待時間設定群組
        self.reconnect_wait_group = QGroupBox(t("reconnect_wait_config", "等待時間設定") + " (s)")
        reconnect_wait_layout = QHBoxLayout()
        self.reconnect_wait_left_form = QFormLayout()
        self.reconnect_wait_right_form = QFormLayout()
        reconnect_wait_left_form = self.reconnect_wait_left_form
        reconnect_wait_right_form = self.reconnect_wait_right_form

        self.action_cooldown_spin = QDoubleSpinBox()
        self.action_cooldown_spin.setRange(0.1, 30.0)
        self.action_cooldown_spin.setDecimals(1)
        self.action_cooldown_spin.setSingleStep(0.1)
        self.action_cooldown_spin.setValue(disconnect_cfg.get("action_cooldown", 1.0))
        self.action_cooldown_spin.valueChanged.connect(self.on_config_changed)
        reconnect_wait_left_form.addRow(t("disconnect_same_screen_timeout_label", "同畫面逾時") + ":", self.same_screen_timeout_spin)
        reconnect_wait_left_form.addRow(t("action_cooldown", "點擊等待時間") + ":", self.action_cooldown_spin)

        reconnect_wait_right_form.addRow(t("pc_launch_wait_timeout", "重啟等待時間") + ":", self.pc_launch_wait_timeout_spin)
        reconnect_wait_right_form.addRow(t("screen_hash_interval", "辨識畫面間隔") + ":", self.screen_hash_interval_spin)

        self.check_game_open_interval_spin = QSpinBox()
        self.check_game_open_interval_spin.setRange(1, 1440)
        self.check_game_open_interval_spin.setSingleStep(1)
        self.check_game_open_interval_spin.setValue(int(disconnect_cfg.get("check_game_open_interval_emu", 60.0)))
        self.check_game_open_interval_spin.valueChanged.connect(self.on_config_changed)
        reconnect_wait_right_form.addRow(t("check_game_open_interval_minutes", "遊戲開啟檢查間隔(分)") + ":", self.check_game_open_interval_spin)

        self.login_timeout_spin = QDoubleSpinBox()
        self.login_timeout_spin.setRange(10.0, 600.0)
        self.login_timeout_spin.setDecimals(0)
        self.login_timeout_spin.setSingleStep(5.0)
        self.login_timeout_spin.setValue(disconnect_cfg.get("login_timeout", 120.0))
        self.login_timeout_spin.valueChanged.connect(self.on_config_changed)
        reconnect_wait_left_form.addRow(t("login_timeout", "登入逾時") + ":", self.login_timeout_spin)

        self.post_login_timeout_spin = QDoubleSpinBox()
        self.post_login_timeout_spin.setRange(10.0, 300.0)
        self.post_login_timeout_spin.setDecimals(0)
        self.post_login_timeout_spin.setSingleStep(5.0)
        self.post_login_timeout_spin.setValue(disconnect_cfg.get("post_login_timeout", 45.0))
        self.post_login_timeout_spin.valueChanged.connect(self.on_config_changed)
        reconnect_wait_left_form.addRow(t("post_login_timeout", "登入後逾時") + ":", self.post_login_timeout_spin)

        reconnect_wait_layout.addLayout(reconnect_wait_left_form)
        reconnect_wait_layout.addLayout(reconnect_wait_right_form)
        self.reconnect_wait_group.setLayout(reconnect_wait_layout)
        reconnect_scroll_layout.addWidget(self.reconnect_wait_group)

        # 隱藏元件（保留功能接口）
        self.restart_game_enable_check = QCheckBox()
        self.restart_game_enable_check.setChecked(disconnect_cfg.get("restart_game_enabled", True))
        self.restart_game_enable_check.stateChanged.connect(self._on_restart_game_feature_changed)
        self.restart_game_reserved_label = QLabel()
        self.login_game_enable_check = QCheckBox()
        self.login_game_enable_check.setChecked(disconnect_cfg.get("login_game_enabled", True))
        self.login_game_enable_check.stateChanged.connect(self._on_login_game_feature_changed)
        self.login_game_reserved_label = QLabel()

        # 自動開啟功能控件（內容顯示於獨立的「自動開啟功能」頁籤）
        self.auto_enable_features_check = QCheckBox(t("reconnect_auto_features_enable", "啟用自動開啟功能"))
        self.auto_enable_features_check.setStyleSheet(
            "font-weight: bold; font-size: 11pt; padding: 4px;"
            "background: #E3F2FD; border-radius: 4px;"
        )
        self.auto_enable_features_check.setChecked(disconnect_cfg.get("auto_enable_features_enabled", True))
        self.auto_enable_features_check.stateChanged.connect(self._on_auto_feature_master_changed)

        self.auto_enable_wander_check = QCheckBox(t("reconnect_auto_wander_enable", "自動開啟徘徊"))
        self.auto_enable_wander_check.setChecked(disconnect_cfg.get("auto_enable_wander", True))
        self.auto_enable_wander_check.stateChanged.connect(self.on_config_changed)

        self.auto_enable_ai_check = QCheckBox(t("reconnect_auto_ai_enable", "自動開啟 AI"))
        self.auto_enable_ai_check.setChecked(disconnect_cfg.get("auto_enable_ai", True))
        self.auto_enable_ai_check.stateChanged.connect(self.on_config_changed)

        self.auto_feature_action_cooldown_spin = QDoubleSpinBox()
        self.auto_feature_action_cooldown_spin.setRange(0.1, 30.0)
        self.auto_feature_action_cooldown_spin.setDecimals(1)
        self.auto_feature_action_cooldown_spin.setSingleStep(0.1)
        self.auto_feature_action_cooldown_spin.setValue(disconnect_cfg.get("auto_feature_action_cooldown", disconnect_cfg.get("action_cooldown", 1.0)))
        self.auto_feature_action_cooldown_spin.valueChanged.connect(self.on_config_changed)

        self.auto_feature_scan_interval_spin = QDoubleSpinBox()
        self.auto_feature_scan_interval_spin.setRange(0.1, 10.0)
        self.auto_feature_scan_interval_spin.setDecimals(1)
        self.auto_feature_scan_interval_spin.setSingleStep(0.1)
        self.auto_feature_scan_interval_spin.setValue(disconnect_cfg.get("auto_feature_scan_interval", 0.6))
        self.auto_feature_scan_interval_spin.valueChanged.connect(self.on_config_changed)

        self.in_game_confirm_timeout_spin = QDoubleSpinBox()
        self.in_game_confirm_timeout_spin.setRange(5.0, 300.0)
        self.in_game_confirm_timeout_spin.setDecimals(0)
        self.in_game_confirm_timeout_spin.setSingleStep(5.0)
        self.in_game_confirm_timeout_spin.setValue(disconnect_cfg.get("in_game_confirm_timeout", 25.0))
        self.in_game_confirm_timeout_spin.valueChanged.connect(self.on_config_changed)

        # 每台設備個別設定
        self.device_auto_feature_group = QGroupBox(t("device_auto_feature_config", "每台設備自動開啟功能"))
        device_auto_feature_inner = QVBoxLayout()
        self.device_auto_feature_info = QLabel(t("device_auto_feature_hint", "先在啟動頁選擇設備，才可設定個別自動開啟功能。"))
        self.device_auto_feature_info.setStyleSheet("color: #666; font-size: 9pt; line-height: 1.6;")
        self.device_auto_feature_info.setWordWrap(True)
        device_auto_feature_inner.addWidget(self.device_auto_feature_info)
        self.device_auto_feature_checks = {}
        self.device_auto_feature_container = QWidget()
        self.device_auto_feature_container_layout = QVBoxLayout(self.device_auto_feature_container)
        device_auto_feature_inner.addWidget(self.device_auto_feature_container)
        self.device_auto_feature_group.setLayout(device_auto_feature_inner)
        self.auto_feature_threshold_keys = [
            "btn_wander_on", "btn_wander_off", "btn_ai", "btn_ai_off_in_battle",
        ]

        # 斷線重連辨識閾值
        self.disconnect_threshold_group = QGroupBox(t("disconnect_threshold_config", "辨識閾值設定"))
        disconnect_threshold_layout = QVBoxLayout()
        self.disconnect_threshold_spinners = {}
        self.disconnect_threshold_labels = {}
        default_disconnect_thresholds = self.default_config.get("thresholds", {}).get("EMU", {})
        disconnect_threshold_names = {
            "disconnect_hint": ("threshold_disconnect_hint", "連線中斷視窗"),
            "btn_reconnect": ("threshold_btn_reconnect", "重新連線按鈕"),
            "btn_back_to_login": ("threshold_btn_back_to_login", "返回登入按鈕"),
            "login_from_other_place": ("threshold_login_from_other_place", "異地登入提示"),
            "multi_login": ("threshold_multi_login", "多元帳號登入"),
            "custom_login": ("threshold_custom_login", "自定義帳號登入"),
            "btn_login_account": ("threshold_btn_login_account", "帳號登入按鈕"),
            "select_server": ("threshold_select_server", "選擇伺服器"),
            "select_character": ("threshold_select_character", "選擇角色"),
            "login_game_button": ("threshold_login_game_button", "進入遊戲按鈕"),
            "pop_gift_box": ("threshold_pop_gift_box", "限時禮盒介面"),
            "start_game_announcement": ("threshold_start_game_announcement", "啟動公告視窗"),
            "announcement": ("threshold_announcement", "公告視窗"),
            "update_resource": ("threshold_update_resource", "更新資源提示"),
            "dont_ask_today": ("threshold_dont_ask_today", "今日不再詢問"),
            "btn_cross": ("threshold_btn_cross", "叉叉按鈕"),
            "btn_power_saving": ("threshold_btn_power_saving", "省電模式按鈕"),
            "btn_wander_on": ("threshold_btn_wander_on", "徘徊開啟"),
            "btn_wander_off": ("threshold_btn_wander_off", "徘徊關閉"),
            "btn_ai": ("threshold_btn_ai", "AI按鈕"),
            "btn_ai_off_in_battle": ("threshold_btn_ai_off_in_battle", "戰鬥中AI關閉"),
        }

        top_threshold_form = QFormLayout()
        self.screen_hash_diff_label = QLabel(t("screen_hash_diff_threshold", "同畫面辨識差異閾值") + ":")
        top_threshold_form.addRow(
            self.screen_hash_diff_label,
            self.screen_hash_diff_threshold_spin,
        )
        disconnect_threshold_layout.addLayout(top_threshold_form)

        def add_threshold_section(section_attr_name, section_i18n_key, section_fallback, keys):
            section_group = QGroupBox(t(section_i18n_key, section_fallback))
            section_layout = QGridLayout()
            section_layout.setHorizontalSpacing(12)
            section_layout.setVerticalSpacing(8)
            for idx, key in enumerate(keys):
                i18n_key, fallback = disconnect_threshold_names[key]
                spinner = QDoubleSpinBox()
                spinner.setRange(0.01, 1.0)
                spinner.setDecimals(2)
                spinner.setSingleStep(0.01)
                spinner.setValue(self.current_config["thresholds_emu"].get(key, default_disconnect_thresholds.get(key, 0.70)))
                spinner.valueChanged.connect(self.on_config_changed)
                tooltip_html = build_template_tooltip_html(key)
                spinner.setToolTip(tooltip_html)
                self._bind_template_preview(spinner, key)
                self.disconnect_threshold_spinners[key] = spinner

                label = QLabel(t(i18n_key, fallback) + ":")
                label.setToolTip(tooltip_html)
                self._bind_template_preview(label, key)
                self.disconnect_threshold_labels[key] = label

                item_widget = QWidget()
                item_layout = QHBoxLayout(item_widget)
                item_layout.setContentsMargins(0, 0, 0, 0)
                item_layout.setSpacing(6)
                item_layout.addWidget(label)
                item_layout.addWidget(spinner)
                section_layout.addWidget(item_widget, idx // 4, idx % 4)

            for col in range(4):
                section_layout.setColumnStretch(col, 1)
            section_group.setLayout(section_layout)
            setattr(self, section_attr_name, section_group)
            disconnect_threshold_layout.addWidget(section_group)

        add_threshold_section(
            "disconnect_threshold_section_a_group",
            "disconnect_threshold_section_a", "斷線提示與返回",
            ["disconnect_hint", "btn_reconnect", "btn_back_to_login", "login_from_other_place"],
        )
        add_threshold_section(
            "disconnect_threshold_section_b_group",
            "disconnect_threshold_section_b", "登入流程",
            ["multi_login", "custom_login", "btn_login_account", "select_server", "select_character",
             "login_game_button", "start_game_announcement", "announcement", "update_resource"],
        )
        add_threshold_section(
            "disconnect_threshold_section_c_group",
            "disconnect_threshold_section_c", "遊戲公告與彈窗",
            ["pop_gift_box", "dont_ask_today", "btn_cross", "btn_power_saving"],
        )
        add_threshold_section(
            "disconnect_threshold_section_d_group",
            "disconnect_threshold_section_d", "辨識閾值設定",
            ["btn_wander_on", "btn_wander_off", "btn_ai", "btn_ai_off_in_battle"],
        )
        disconnect_threshold_layout.removeWidget(self.disconnect_threshold_section_d_group)
        self.disconnect_threshold_section_d_group.setParent(None)

        self.disconnect_threshold_group.setLayout(disconnect_threshold_layout)
        reconnect_scroll_layout.addWidget(self.disconnect_threshold_group)

        reconnect_scroll_layout.addStretch()
        reconnect_scroll.setWidget(reconnect_scroll_widget)
        reconnect_layout.addWidget(reconnect_scroll)
        reconnect_tab.setLayout(reconnect_layout)

        # =============================================
        # === 自動開啟功能頁籤 ===
        # =============================================
        auto_features_top_tab = QWidget()
        auto_features_top_layout = QVBoxLayout()
        auto_features_top_layout.addWidget(self.auto_enable_features_check)

        auto_features_scroll = QScrollArea()
        auto_features_scroll.setWidgetResizable(True)
        auto_features_scroll_widget = QWidget()
        auto_features_scroll_layout = QVBoxLayout(auto_features_scroll_widget)
        auto_features_scroll_layout.setContentsMargins(0, 0, 0, 0)
        auto_features_scroll_layout.setSpacing(8)

        self.auto_features_content_group = QGroupBox()
        self.auto_features_content_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        auto_features_group_layout = QVBoxLayout()
        auto_features_group_layout.setSpacing(8)
        auto_features_group_layout.setContentsMargins(8, 8, 8, 8)
        auto_features_sub_container = QWidget()
        auto_features_sub_layout = QVBoxLayout(auto_features_sub_container)
        auto_features_sub_layout.setContentsMargins(16, 4, 0, 4)
        auto_features_sub_layout.setSpacing(4)
        auto_features_sub_layout.addWidget(self.auto_enable_wander_check)
        auto_features_sub_layout.addWidget(self.auto_enable_ai_check)
        auto_features_group_layout.addWidget(auto_features_sub_container)

        self.auto_feature_wait_group = QGroupBox(t("wait_time_config", "等待時間設定") + " (s)")
        self.auto_feature_wait_form = QFormLayout()

        self.auto_feature_action_cooldown_label = QLabel(t("auto_feature_action_cooldown", "點擊等待時間") + ":")
        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(6)
        action_row.addWidget(self.auto_feature_action_cooldown_label)
        action_row.addWidget(self.auto_feature_action_cooldown_spin)
        action_row.addStretch()
        self.auto_feature_wait_form.addRow(action_row)

        self.auto_feature_scan_interval_label = QLabel(t("auto_feature_scan_interval", "辨識畫面間隔") + ":")
        scan_row = QHBoxLayout()
        scan_row.setContentsMargins(0, 0, 0, 0)
        scan_row.setSpacing(6)
        scan_row.addWidget(self.auto_feature_scan_interval_label)
        scan_row.addWidget(self.auto_feature_scan_interval_spin)
        scan_row.addStretch()
        self.auto_feature_wait_form.addRow(scan_row)

        self.in_game_confirm_timeout_label = QLabel(t("in_game_confirm_timeout", "遊戲內確認逾時") + ":")
        confirm_row = QHBoxLayout()
        confirm_row.setContentsMargins(0, 0, 0, 0)
        confirm_row.setSpacing(6)
        confirm_row.addWidget(self.in_game_confirm_timeout_label)
        confirm_row.addWidget(self.in_game_confirm_timeout_spin)
        confirm_row.addStretch()
        self.auto_feature_wait_form.addRow(confirm_row)
        self.auto_feature_wait_group.setLayout(self.auto_feature_wait_form)
        auto_features_group_layout.addWidget(self.auto_feature_wait_group, 0)

        auto_features_group_layout.addWidget(self.disconnect_threshold_section_d_group, 0)
        auto_features_group_layout.addWidget(self.device_auto_feature_group, 0)
        auto_features_group_layout.addStretch()
        self.auto_features_content_group.setLayout(auto_features_group_layout)

        auto_features_scroll_layout.addWidget(self.auto_features_content_group)
        auto_features_scroll_layout.addStretch()
        auto_features_scroll.setWidget(auto_features_scroll_widget)

        auto_features_top_layout.addWidget(auto_features_scroll)
        auto_features_top_tab.setLayout(auto_features_top_layout)

        # =============================================
        self.config_subtabs.addTab(auto_tab, t("settings_auto_battle_tab", "自動玩家對戰"))
        self.config_subtabs.addTab(reconnect_tab, t("settings_disconnect_tab", "斷線重連"))
        self.config_subtabs.addTab(auto_features_top_tab, t("settings_auto_features_tab", "自動開啟功能"))
        layout.addWidget(self.config_subtabs)

        # === 保存/重置按鈕 ===
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton(t("config_change", "保存設定"))
        self.save_btn.clicked.connect(self.save_config)
        self.save_btn.setEnabled(False)
        button_layout.addWidget(self.save_btn)

        self.reset_btn = QPushButton(t("btn_reset_changes", "重置變更"))
        self.reset_btn.clicked.connect(self.reset_changes)
        button_layout.addWidget(self.reset_btn)

        self.restore_btn = QPushButton(t("btn_restore_defaults", "恢復預設"))
        self.restore_btn.clicked.connect(self.restore_defaults)
        button_layout.addWidget(self.restore_btn)

        layout.addLayout(button_layout)

        widget.setLayout(layout)

        self._update_auto_battle_tab_enabled()
        self._update_reconnect_tab_enabled()
        self._update_auto_features_tab_enabled()
        self._on_unlimited_changed()

        return widget

    # ── 控制台頁 ───────────────────────────────────────────────
    def create_console_tab(self):
        """控制台標籤"""
        widget = QWidget()
        layout = QVBoxLayout()

        self.log_group = QGroupBox(t("error", "輸出日誌"))
        log_layout = QVBoxLayout()

        filter_layout = QHBoxLayout()
        self.log_filter_level_label = QLabel(t("log_filter_level", "層級篩選") + ":")
        filter_layout.addWidget(self.log_filter_level_label)
        self.log_filter_level_combo = QComboBox()
        self.log_filter_level_combo.addItems([
            t("log_level_all", "全部"),
            "ERROR", "WARN", "INFO", "START", "STOP", "PAUSE", "RESUME", "DETECT",
            "DEBUG", "STATE", "DISCONNECT", "FLOW", "SEARCH", "BATTLE", "TIME",
            "WAIT", "STAT", "ENERGY", "CLICK", "LOCK", "SKIP", "OK", "TEST", "CONFIG",
        ])
        self.log_filter_level_combo.currentIndexChanged.connect(self._refresh_log_view)
        filter_layout.addWidget(self.log_filter_level_combo)

        self.log_filter_keyword_label = QLabel(t("log_filter_keyword", "關鍵字") + ":")
        filter_layout.addWidget(self.log_filter_keyword_label)
        self.log_filter_input = QLineEdit()
        self.log_filter_input.setPlaceholderText(t("log_filter_keyword_placeholder", "輸入關鍵字即時過濾"))
        self.log_filter_input.textChanged.connect(self._refresh_log_view)
        filter_layout.addWidget(self.log_filter_input)

        self.log_filter_clear_btn = QPushButton(t("log_filter_clear", "清除篩選"))
        self.log_filter_clear_btn.clicked.connect(self._clear_log_filter)
        filter_layout.addWidget(self.log_filter_clear_btn)
        log_layout.addLayout(filter_layout)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(_QFont("Courier", 9))
        log_layout.addWidget(self.log_text)

        self.clear_log_btn = QPushButton(t("btn_clear_log", "清空日誌"))
        self.clear_log_btn.clicked.connect(self._clear_logs)
        log_layout.addWidget(self.clear_log_btn)

        self.log_group.setLayout(log_layout)
        layout.addWidget(self.log_group)

        widget.setLayout(layout)
        return widget

    # ── 說明頁 ─────────────────────────────────────────────────
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

{t("version_label", "版本")}: v{APP_VERSION}

【{t("help_highlights_title", "功能重點")}】
- {t("help_highlight_1", "PC GUI、EMU GUI、CMD 三種模式分離運作")}
- {t("help_highlight_2", "自動玩家對戰、斷線重連、自動開啟功能可分頁設定")}
- {t("help_highlight_3", "支援分頁儲存、重置變更、恢復預設與未儲存防呆")}
- {t("help_highlight_4", "補強登入後彈窗、低活力補充、遊戲開啟檢查與功能恢復")}
- {t("help_highlight_5", "更新模板、多語系、視窗位置記憶與 Debug 日誌效能")}

{t("help_ldplayer_only", "★ 僅支援 LDPlayer（雷電模擬器）")}

【{t("help_shortcuts", "快捷鍵")}】
- {t("start_stop_command", "Ctrl+C - 啟動/停止")}
- {t("pause_command", "Ctrl+P - 暫停/繼續")}
- {t("debug_command", "Ctrl+D - 除錯模式")}

【{t("help_tips", "小提示")}】
- {t("help_tip1", "首次使用可先調整閾值與等待時間")}
- {t("help_tip2", "若辨識失敗可調整閾值")}
- {t("help_ldplayer_path_tip", "若 LDPlayer 安裝在非預設路徑，請在「啟動」頁面指定安裝路徑")}

【{t("help_usage_limits", "使用限制")}】
- {t("help_limit_no_power_saving", "請勿開啟省電模式")}
- {t("help_limit_lang_zh_tw", "遊戲語言必須使用繁體中文")}
        """)
