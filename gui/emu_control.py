"""
gui/emu_control.py
EmuControlMixin - EMU 模式設備掃描、機器人控制、快捷鍵、UI 狀態管理 mixin
"""

import os
import time
from copy import deepcopy

from PyQt5.QtWidgets import QMessageBox, QListWidgetItem, QLabel, QFileDialog
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from i18n import t

from gui.shared import resource_path, AUTOPVE_AVAILABLE, autoPVE
from gui.emu_threads import DetectThread, BotControlThread


class EmuControlMixin:
    """EMU 模式控制 mixin：設備管理、機器人控制、快捷鍵與 UI 啟/停用"""

    def apply_app_icon(self):
        """設置應用圖標"""
        try:
            icon_path = resource_path("app.ico")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

    # ── 事件處理 ───────────────────────────────────────────────
    def _on_auto_battle_enable_changed(self):
        """自動玩家對戰主開關切換"""
        self._update_auto_battle_tab_enabled()
        self.on_config_changed()

    def _on_disconnect_enable_changed(self):
        """斷線重連主開關切換"""
        if self.disconnect_enable_check.isChecked():
            self.restart_game_enable_check.blockSignals(True)
            self.restart_game_enable_check.setChecked(True)
            self.restart_game_enable_check.blockSignals(False)
            self.login_game_enable_check.blockSignals(True)
            self.login_game_enable_check.setChecked(True)
            self.login_game_enable_check.blockSignals(False)
        self._ensure_reconnect_core_flows()
        self._update_reconnect_tab_enabled()
        self.on_config_changed()

    def _on_unlimited_changed(self):
        """無限重試切換"""
        self._update_reconnect_tab_enabled()
        self.on_config_changed()

    def _ensure_reconnect_core_flows(self):
        """避免主開關啟用但重連核心流程全關。"""
        if not self.disconnect_enable_check.isChecked():
            return
        if self.restart_game_enable_check.isChecked() and self.login_game_enable_check.isChecked():
            return
        self.restart_game_enable_check.blockSignals(True)
        self.restart_game_enable_check.setChecked(True)
        self.restart_game_enable_check.blockSignals(False)
        self.login_game_enable_check.blockSignals(True)
        self.login_game_enable_check.setChecked(True)
        self.login_game_enable_check.blockSignals(False)
        self.append_log(t("auto_enable_reconnect_core_flows_msg", "[CONFIG] 已自動啟用「重開遊戲」與「登入遊戲」，確保斷線重連流程完整。"))

    def _on_restart_game_feature_changed(self):
        self._ensure_reconnect_core_flows()
        self.on_config_changed()

    def _on_login_game_feature_changed(self):
        self._ensure_reconnect_core_flows()
        self.on_config_changed()

    def _on_auto_feature_master_changed(self):
        self._update_auto_features_tab_enabled()
        self.on_config_changed()

    # ── Tab 啟/停用 ────────────────────────────────────────────
    def _update_auto_battle_tab_enabled(self):
        """根據自動玩家對戰主開關，啟用/停用該頁所有控件"""
        enabled = self.auto_battle_enable_check.isChecked()
        for spinner in self.wait_spinners.values():
            spinner.setEnabled(enabled)
        for spinner in self.threshold_spinners.values():
            spinner.setEnabled(enabled)
        self.energy_check.setEnabled(enabled)
        for check in self.device_energy_checks.values():
            check.setEnabled(enabled)
        for path_input in self.emulator_path_inputs.values():
            path_input.setEnabled(not self.is_running)
        for btn in self.browse_buttons.values():
            btn.setEnabled(not self.is_running)

    def _update_reconnect_tab_enabled(self):
        """根據斷線重連主開關，啟用/停用該頁所有控件"""
        enabled = self.disconnect_enable_check.isChecked()
        self.same_screen_timeout_spin.setEnabled(enabled)
        self.pc_launch_wait_timeout_spin.setEnabled(enabled and not self.is_running)
        unlimited = self.max_reconnect_unlimited_check.isChecked()
        self.max_reconnect_attempts_spin.setEnabled(enabled and not unlimited)
        self.max_reconnect_unlimited_check.setEnabled(enabled)
        self.emu_package_input.setEnabled(not self.is_running)
        self.screen_hash_diff_threshold_spin.setEnabled(enabled)
        self.screen_hash_interval_spin.setEnabled(enabled)
        self.action_cooldown_spin.setEnabled(enabled)
        self.check_game_open_interval_spin.setEnabled(enabled and not self.is_running)
        self.login_timeout_spin.setEnabled(enabled)
        self.post_login_timeout_spin.setEnabled(enabled)
        for key, spinner in self.disconnect_threshold_spinners.items():
            if key not in self.auto_feature_threshold_keys:
                spinner.setEnabled(enabled)

    def _update_auto_features_tab_enabled(self):
        """根據自動開啟功能主開關，啟用/停用子控件（獨立於斷線重連開關）"""
        enabled = self.auto_enable_features_check.isChecked()
        self.auto_enable_wander_check.setEnabled(enabled)
        self.auto_enable_ai_check.setEnabled(enabled)
        self.auto_feature_action_cooldown_spin.setEnabled(enabled)
        self.auto_feature_scan_interval_spin.setEnabled(enabled)
        self.in_game_confirm_timeout_spin.setEnabled(enabled)
        for key in self.auto_feature_threshold_keys:
            if key in self.disconnect_threshold_spinners:
                self.disconnect_threshold_spinners[key].setEnabled(enabled)
        for widgets in self.device_auto_feature_checks.values():
            widgets["wander"].setEnabled(enabled)
            widgets["ai"].setEnabled(enabled)

    def _update_run_action_guard(self):
        """未儲存設定時禁止啟動或繼續，並在狀態列提示。"""
        if not hasattr(self, "start_btn") or not hasattr(self, "pause_btn") or not hasattr(self, "status_label"):
            return

        blocked = bool(self.config_dirty)

        if not self.is_running:
            self.start_btn.setEnabled((len(self.selected_devices) > 0) and (not blocked))
            if blocked:
                self.status_label.setText(t("status_unsaved_block", "有未儲存設定，請先儲存或重置後再啟動"))
                self.status_label.setStyleSheet("background-color: #FFD54F; color: black; padding: 8px; border-radius: 4px;")
            elif len(self.selected_devices) > 0:
                self.status_label.setText(t("devices_detected_ready", "已偵測到設備，可開始設定或啟動"))
                self.status_label.setStyleSheet("background-color: #90EE90; color: black; padding: 8px; border-radius: 4px;")
            return

        if self.is_paused:
            self.pause_btn.setEnabled(not blocked)
            if blocked:
                self.status_label.setText(t("status_unsaved_block_resume", "有未儲存設定，請先儲存或重置後再繼續"))
                self.status_label.setStyleSheet("background-color: #FFD54F; color: black; padding: 8px; border-radius: 4px;")
            else:
                self.status_label.setText(t("paused", "已暫停"))
                self.status_label.setStyleSheet("background-color: #FFD54F; color: black; padding: 8px; border-radius: 4px;")
        else:
            self.pause_btn.setEnabled(True)

    # ── 設備偵測 ───────────────────────────────────────────────
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

        # 若僅偵測到一台設備，預設自動勾選。
        if self.device_list.count() == 1:
            item = self.device_list.item(0)
            if item is not None:
                item.setCheckState(Qt.Checked)
                self.on_device_selection_changed(item)

        count = len(devices)
        self.append_log(f"[DETECT] 找到 {count} 台設備")
        if count == 0:
            self.status_label.setText(t("no_device_detected", "未偵測到設備，請確認 ADB 已開啟"))
            self.status_label.setStyleSheet("background-color: #FFD54F; color: black; padding: 8px; border-radius: 4px;")
        elif not self.is_running and not self.config_dirty:
            self.status_label.setText(t("devices_detected_ready", "已偵測到設備，可開始設定或啟動"))
            self.status_label.setStyleSheet("background-color: #90EE90; color: black; padding: 8px; border-radius: 4px;")
        self._update_run_action_guard()

    def toggle_select_all(self, state):
        """全選/取消全選 - 僅回應用戶手動操作"""
        if not self.select_all_checkbox.hasFocus():
            return
        self.device_list.blockSignals(True)
        new_state = Qt.Checked if state != Qt.Unchecked else Qt.Unchecked
        for i in range(self.device_list.count()):
            self.device_list.item(i).setCheckState(new_state)
        self.device_list.blockSignals(False)
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

        self.select_all_checkbox.blockSignals(True)
        if total_count > 0 and checked_count == total_count:
            self.select_all_checkbox.setCheckState(Qt.Checked)
        else:
            self.select_all_checkbox.setCheckState(Qt.Unchecked)
        self.select_all_checkbox.blockSignals(False)

        self.update_device_energy_settings()
        self.update_device_auto_feature_settings()
        self._update_run_action_guard()

    # ── 機器人控制 ─────────────────────────────────────────────
    def on_start_stop(self):
        """啟動/停止"""
        if self.is_running:
            self.stop_bot()
        else:
            if self.config_dirty:
                self.append_log("[CONFIG] " + t("status_unsaved_block", "有未儲存設定，請先儲存或重置後再啟動"))
                self._update_run_action_guard()
                return
            if len(self.selected_devices) == 0:
                QMessageBox.warning(self, "Warning", t("status_none_selected", "請至少選擇一台設備"))
                return
            self.start_bot()

    def _build_config(self):
        """從 UI 控件收集配置"""
        unlimited = self.max_reconnect_unlimited_check.isChecked()
        config = {
            "wait_times": {k: s.value() for k, s in self.wait_spinners.items()},
            "energy_strategy": self.energy_check.isChecked(),
            "auto_battle_enabled": self.auto_battle_enable_check.isChecked(),
            "thresholds": {
                "EMU": {
                    **{k: s.value() for k, s in self.threshold_spinners.items()},
                    **{k: s.value() for k, s in self.disconnect_threshold_spinners.items()},
                }
            },
            "disconnect": {
                "enabled": self.disconnect_enable_check.isChecked(),
                "same_screen_timeout": self.same_screen_timeout_spin.value(),
                "max_reconnect_attempts": 0 if unlimited else int(self.max_reconnect_attempts_spin.value()),
                "pc_launch_wait_timeout": self.pc_launch_wait_timeout_spin.value(),
                "restart_game_enabled": self.restart_game_enable_check.isChecked(),
                "login_game_enabled": self.login_game_enable_check.isChecked(),
                "auto_enable_features_enabled": self.auto_enable_features_check.isChecked(),
                "auto_enable_wander": self.auto_enable_wander_check.isChecked(),
                "auto_enable_ai": self.auto_enable_ai_check.isChecked(),
                "emu_package_name": self.emu_package_input.text().strip(),
                "screen_hash_diff_threshold": self.screen_hash_diff_threshold_spin.value(),
                "screen_hash_interval": self.screen_hash_interval_spin.value(),
                "action_cooldown": self.action_cooldown_spin.value(),
                "auto_feature_action_cooldown": self.auto_feature_action_cooldown_spin.value(),
                "auto_feature_scan_interval": self.auto_feature_scan_interval_spin.value(),
                "check_game_open_interval_emu": float(self.check_game_open_interval_spin.value()),
                "login_timeout": self.login_timeout_spin.value(),
                "post_login_timeout": self.post_login_timeout_spin.value(),
                "in_game_confirm_timeout": self.in_game_confirm_timeout_spin.value(),
            },
        }
        device_configs = {}
        for serial, check in self.device_energy_checks.items():
            device_configs[serial] = check.isChecked()
        if device_configs:
            config["device_configs"] = device_configs
        device_auto_features = {}
        for serial, widgets in self.device_auto_feature_checks.items():
            device_auto_features[serial] = {
                "wander": widgets["wander"].isChecked(),
                "ai": widgets["ai"].isChecked(),
            }
        if device_auto_features:
            config["device_auto_features"] = device_auto_features
        return config

    def start_bot(self):
        """啟動機器人"""
        self.is_running = True
        self.is_paused = False
        if AUTOPVE_AVAILABLE:
            try:
                autoPVE.set_paused(False)
                autoPVE.set_debug_mode(self.is_debug)
            except Exception:
                pass
        self.start_btn.setText(t("btn_stop", "停止"))
        self.start_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px; font-weight: bold;")
        self.pause_btn.setEnabled(True)
        self.pause_btn.setText(t("btn_pause", "暫停"))
        self.pause_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 10px; font-weight: bold;")
        self.refresh_btn.setEnabled(False)
        self.status_label.setText(t("resumed", "執行中"))
        self.status_label.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px; border-radius: 4px;")

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
        self.is_paused = False
        if AUTOPVE_AVAILABLE:
            try:
                autoPVE.set_paused(False)
            except Exception:
                pass
        if self.bot_thread:
            self.bot_thread.stop()
            self.bot_thread.wait(2000)
            self.bot_thread = None
        self.start_btn.setText(t("btn_start", "啟動"))
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-weight: bold;")
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText(t("btn_pause", "暫停"))
        self.pause_btn.setStyleSheet("background-color: #9E9E9E; color: #CCCCCC; padding: 10px; font-weight: bold;")
        self.refresh_btn.setEnabled(True)
        self.status_label.setText(t("stopped", "已停止"))
        self.status_label.setStyleSheet("background-color: #FF6B6B; color: white; padding: 8px; border-radius: 4px;")

        self.set_launch_tab_enabled(True)
        self.set_config_editing_enabled(True)

        self.start_btn.setEnabled(len(self.selected_devices) > 0)
        self._update_run_action_guard()
        self.append_log("[STOP] 已停止")

    def on_bot_finished(self):
        """Bot 執行完畢時更新 UI"""
        if self.is_running:
            self.stop_bot()

    def on_pause(self):
        """暫停/繼續"""
        if not self.is_running:
            return
        now = time.time()
        if now - self._last_pause_toggle_ts < self._pause_toggle_cooldown:
            return
        self._last_pause_toggle_ts = now

        if self.is_paused and self.config_dirty:
            self.append_log("[CONFIG] " + t("status_unsaved_block_resume", "有未儲存設定，請先儲存或重置後再繼續"))
            self._update_run_action_guard()
            return

        self.is_paused = not self.is_paused
        if AUTOPVE_AVAILABLE:
            try:
                autoPVE.set_paused(self.is_paused)
            except Exception:
                pass
        if self.is_paused:
            self.pause_btn.setText(t("btn_resume", "繼續執行"))
            self.pause_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px; font-weight: bold;")
            self.status_label.setText(t("paused", "已暫停"))
            self.status_label.setStyleSheet("background-color: #FFD54F; color: black; padding: 8px; border-radius: 4px;")
            self.set_config_editing_enabled(True)
            self.append_log("[PAUSE] 已暫停")
        else:
            self.pause_btn.setText(t("btn_pause", "暫停"))
            self.pause_btn.setStyleSheet("background-color: #FF9800; color: white; padding: 10px; font-weight: bold;")
            self.status_label.setText(t("resumed", "執行中"))
            self.status_label.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px; border-radius: 4px;")
            self.set_config_editing_enabled(False)
            # 恢復時固定同步一次，避免「暫停期間已儲存」導致 config_dirty=False 而漏推送。
            self._push_config_update()
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

    # ── 快捷鍵 ─────────────────────────────────────────────────
    def _shortcut_start_stop(self):
        self.on_start_stop()

    def _shortcut_pause(self):
        if self.is_running:
            self.on_pause()

    def _shortcut_debug(self):
        self.on_debug()

    def _push_config_update(self):
        """將 UI 當前設定推送至 RUNNING_CONFIG，讓暫停期間的修改立即生效。"""
        if not AUTOPVE_AVAILABLE:
            return
        try:
            cfg = self._build_config()
            rc = autoPVE.RUNNING_CONFIG
            if rc is None:
                return
            for key in ("wait_times", "disconnect"):
                if key in cfg:
                    if key not in rc:
                        rc[key] = {}
                    rc[key].update(cfg[key])
            if "energy_strategy" in cfg:
                rc["energy_strategy"] = cfg["energy_strategy"]
            if "auto_battle_enabled" in cfg:
                rc["auto_battle_enabled"] = cfg["auto_battle_enabled"]
            if "device_configs" in cfg:
                rc["device_configs"] = dict(cfg["device_configs"])
            if "device_auto_features" in cfg:
                rc["device_auto_features"] = dict(cfg["device_auto_features"])
            if "thresholds" in cfg:
                for platform, values in cfg["thresholds"].items():
                    if platform not in rc.get("thresholds", {}):
                        rc.setdefault("thresholds", {})[platform] = {}
                    rc["thresholds"][platform].update(values)
            if self.bot_thread and getattr(self.bot_thread, "bots", None):
                for bot in self.bot_thread.bots:
                    if hasattr(bot, "refresh_runtime_config"):
                        bot.refresh_runtime_config()
        except Exception:
            pass

    def browse_emulator_path(self, emulator_key):
        """瀏覽並選擇 LDPlayer 路徑"""
        directory = QFileDialog.getExistingDirectory(
            self,
            t("ldplayer_install_path", "LDPlayer 安裝路徑設定"),
            ""
        )
        if directory:
            self.emulator_path_inputs[emulator_key].setText(directory)

    # ── UI 啟/停用 ─────────────────────────────────────────────
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
        self.auto_battle_enable_check.setEnabled(enabled)
        self.disconnect_enable_check.setEnabled(enabled)
        reconnect_enabled = enabled and self.disconnect_enable_check.isChecked()
        self.same_screen_timeout_spin.setEnabled(reconnect_enabled)
        self.pc_launch_wait_timeout_spin.setEnabled(reconnect_enabled and not self.is_running)
        unlimited = self.max_reconnect_unlimited_check.isChecked()
        self.max_reconnect_attempts_spin.setEnabled(reconnect_enabled and not unlimited)
        self.max_reconnect_unlimited_check.setEnabled(reconnect_enabled)
        self.emu_package_input.setEnabled(enabled and not self.is_running)
        self.screen_hash_diff_threshold_spin.setEnabled(reconnect_enabled)
        self.screen_hash_interval_spin.setEnabled(reconnect_enabled)
        self.action_cooldown_spin.setEnabled(reconnect_enabled)
        self.check_game_open_interval_spin.setEnabled(reconnect_enabled and not self.is_running)
        self.login_timeout_spin.setEnabled(reconnect_enabled)
        self.post_login_timeout_spin.setEnabled(reconnect_enabled)
        self.auto_enable_features_check.setEnabled(enabled)
        if enabled:
            self._update_auto_features_tab_enabled()
        else:
            self.auto_enable_wander_check.setEnabled(False)
            self.auto_enable_ai_check.setEnabled(False)
            self.auto_feature_action_cooldown_spin.setEnabled(False)
            self.auto_feature_scan_interval_spin.setEnabled(False)
            self.in_game_confirm_timeout_spin.setEnabled(False)
            for widgets in self.device_auto_feature_checks.values():
                widgets["wander"].setEnabled(False)
                widgets["ai"].setEnabled(False)
        for key, spinner in self.disconnect_threshold_spinners.items():
            if key in self.auto_feature_threshold_keys:
                spinner.setEnabled(enabled and self.auto_enable_features_check.isChecked())
            else:
                spinner.setEnabled(reconnect_enabled)
        for check in self.device_energy_checks.values():
            check.setEnabled(enabled)
        for path_input in self.emulator_path_inputs.values():
            path_input.setEnabled(enabled and not self.is_running)
        for btn in self.browse_buttons.values():
            btn.setEnabled(enabled and not self.is_running)
        self.save_btn.setEnabled(enabled and self.config_dirty)
        self.reset_btn.setEnabled(enabled and self.config_dirty)
        self.restore_btn.setEnabled(enabled)
        if hasattr(self, "launch_save_btn"):
            self.launch_save_btn.setEnabled(enabled and self.config_dirty)
        if hasattr(self, "launch_reset_btn"):
            self.launch_reset_btn.setEnabled(enabled and self.config_dirty)
        if hasattr(self, "launch_restore_btn"):
            self.launch_restore_btn.setEnabled(enabled)
        self._update_run_action_guard()

    def closeEvent(self, event):
        """關閉事件"""
        from PyQt5.QtCore import QSettings
        QSettings("WLREHelperBot", "EMUWindow").setValue("geometry", self.saveGeometry())
        if self.bot_thread:
            self.bot_thread.stop()
            self.bot_thread.wait()
        event.accept()


