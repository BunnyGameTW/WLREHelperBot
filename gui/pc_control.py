"""
gui/pc_control.py
PCControlMixin - PC 模式控制邏輯 mixin
"""

import os
import time

from PyQt5.QtWidgets import QMessageBox, QFileDialog
from PyQt5.QtGui import QIcon

from i18n import t

from gui.shared import resource_path, AUTOPVE_AVAILABLE

if AUTOPVE_AVAILABLE:
    import autoPVE


class PCControlMixin:
    """PC 模式控制邏輯 mixin"""

    # ── 圖示 ─────────────────────────────────────────────────
    def apply_app_icon(self):
        try:
            icon_path = resource_path("app.ico")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

    # ── 主開關切換 ─────────────────────────────────────────────
    def _on_auto_battle_enable_changed(self):
        self._update_auto_battle_tab_enabled()
        self.on_config_changed()

    def _on_disconnect_enable_changed(self):
        self._ensure_reconnect_core_flows()
        self._update_reconnect_tab_enabled()
        self.on_config_changed()

    def _on_unlimited_changed(self):
        unlimited = self.max_reconnect_unlimited_check.isChecked()
        self.max_reconnect_attempts_spin.setEnabled(not unlimited)
        self.on_config_changed()

    def _ensure_reconnect_core_flows(self):
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
        self.append_log(t("auto_enable_reconnect_core_flows_msg",
                          "[CONFIG] 已自動啟用「重開遊戲」與「登入遊戲」，確保斷線重連流程完整。"))

    def _on_restart_game_feature_changed(self):
        self._ensure_reconnect_core_flows()
        self.on_config_changed()

    def _on_login_game_feature_changed(self):
        self._ensure_reconnect_core_flows()
        self.on_config_changed()

    def _on_auto_feature_master_changed(self):
        self._update_auto_features_tab_enabled()
        self.on_config_changed()

    # ── 頁籤啟用狀態 ───────────────────────────────────────────
    def _update_auto_battle_tab_enabled(self):
        enabled = self.auto_battle_enable_check.isChecked()
        for spinner in self.wait_spinners.values():
            spinner.setEnabled(enabled)
        for spinner in self.threshold_spinners.values():
            spinner.setEnabled(enabled)
        self.energy_check.setEnabled(enabled)

    def _update_reconnect_tab_enabled(self):
        enabled = self.disconnect_enable_check.isChecked()
        unlimited = self.max_reconnect_unlimited_check.isChecked()
        self.same_screen_timeout_spin.setEnabled(enabled)
        self.pc_launch_wait_timeout_spin.setEnabled(enabled and not self.is_running)
        self.max_reconnect_attempts_spin.setEnabled(enabled and not unlimited)
        self.max_reconnect_unlimited_check.setEnabled(enabled)
        # PC EXE path is launch-tab config and should not be locked by reconnect toggle.
        self.pc_exe_path_input.setEnabled(not self.is_running)
        self.pc_exe_browse_btn.setEnabled(not self.is_running)
        self.screen_hash_diff_threshold_spin.setEnabled(enabled)
        self.screen_hash_interval_spin.setEnabled(enabled)
        self.action_cooldown_spin.setEnabled(enabled)
        self.check_game_open_interval_spin.setEnabled(enabled and not self.is_running)
        if hasattr(self, "scheduled_restart_global_enable_check"):
            self.scheduled_restart_global_enable_check.setEnabled(enabled)
        if hasattr(self, "scheduled_restart_hours_spin"):
            self.scheduled_restart_hours_spin.setEnabled(enabled)
        if hasattr(self, "scheduled_restart_minutes_spin"):
            self.scheduled_restart_minutes_spin.setEnabled(enabled)
        self.login_timeout_spin.setEnabled(enabled)
        self.post_login_timeout_spin.setEnabled(enabled)
        self.restart_game_enable_check.setEnabled(enabled)
        self.login_game_enable_check.setEnabled(enabled)
        for key, spinner in self.disconnect_threshold_spinners.items():
            if key not in self.auto_feature_threshold_keys:
                spinner.setEnabled(enabled)

    def _update_auto_features_tab_enabled(self, editing_enabled=True):
        """根據自動開啟功能主開關，啟用/停用子控件（獨立於斷線重連開關）。"""
        enabled = editing_enabled and self.auto_enable_features_check.isChecked()
        self.auto_enable_wander_check.setEnabled(enabled)
        self.auto_enable_ai_check.setEnabled(enabled)
        self.auto_feature_action_cooldown_spin.setEnabled(enabled)
        self.auto_feature_scan_interval_spin.setEnabled(enabled)
        self.in_game_confirm_timeout_spin.setEnabled(enabled)
        for key in self.auto_feature_threshold_keys:
            if key in self.disconnect_threshold_spinners:
                self.disconnect_threshold_spinners[key].setEnabled(enabled)

    def _update_run_action_guard(self):
        """未儲存設定時禁止啟動或繼續，並在狀態列提示。"""
        if not hasattr(self, "start_btn") or not hasattr(self, "pause_btn") or not hasattr(self, "status_label"):
            return

        blocked = bool(self.config_dirty)

        if not self.is_running:
            self.start_btn.setEnabled((len(self.selected_windows) > 0) and (not blocked))
            if blocked:
                self.status_label.setText(t("status_unsaved_block", "有未儲存設定，請先儲存或重置後再啟動"))
                self.status_label.setStyleSheet("background-color: #FFD54F; color: black; padding: 8px; border-radius: 4px;")
            elif len(self.selected_windows) > 0:
                self.status_label.setText(t("windows_detected_ready", "已偵測到遊戲視窗，可開始設定或啟動"))
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

    # ── 視窗刷新 ───────────────────────────────────────────────
    def refresh_windows(self):
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
            try:
                import win32gui  # type: ignore[reportMissingImports]
                windows = {}

                def enum_windows(hwnd, _lParam):
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        if title and "飄流幻境" in title:
                            windows[hwnd] = title
                    return True

                win32gui.EnumWindows(enum_windows, None)
                self.window_map = windows
            except Exception:
                self.window_map = {}

        from PyQt5.QtWidgets import QListWidgetItem
        from PyQt5.QtCore import Qt
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

        if len(self.window_map) == 0:
            self.status_label.setText(t("no_game_window_detected", "未偵測到遊戲視窗，請先開啟遊戲"))
            self.status_label.setStyleSheet("background-color: #FFD54F; color: black; padding: 8px; border-radius: 4px;")
        elif not self.is_running:
            self.status_label.setText(t("windows_detected_ready", "已偵測到遊戲視窗，可開始設定或啟動"))
            self.status_label.setStyleSheet("background-color: #90EE90; color: black; padding: 8px; border-radius: 4px;")

        # 若只偵測到一個視窗，自動勾選
        if self.window_list.count() == 1:
            item = self.window_list.item(0)
            from PyQt5.QtCore import Qt
            item.setCheckState(Qt.Checked)
            self.on_window_selection_changed(item)
        elif hasattr(self, "update_device_feature_profile_settings"):
            self.update_device_feature_profile_settings()

        self._update_run_action_guard()

    def on_window_selection_changed(self, item):
        """PC 多選：可同時選擇多個遊戲視窗。"""
        from PyQt5.QtCore import Qt

        self.selected_windows = []
        for i in range(self.window_list.count()):
            it = self.window_list.item(i)
            if it.checkState() == Qt.Checked:
                hwnd = it.data(Qt.UserRole)
                if hwnd is not None:
                    self.selected_windows.append(hwnd)

        self.start_btn.setEnabled(len(self.selected_windows) > 0 and not self.is_running)
        if hasattr(self, "update_device_feature_profile_settings"):
            self.update_device_feature_profile_settings()
        self._update_run_action_guard()

    # ── 設定建構 ───────────────────────────────────────────────
    def _build_config(self):
        unlimited = self.max_reconnect_unlimited_check.isChecked()
        config = {
            "wait_times": {k: s.value() for k, s in self.wait_spinners.items()},
            "energy_strategy": self.energy_check.isChecked(),
            "auto_battle_enabled": self.auto_battle_enable_check.isChecked(),
            "thresholds": {
                "PC": {
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
                "pc_exe_path": self.pc_exe_path_input.text().strip(),
                "screen_hash_diff_threshold": self.screen_hash_diff_threshold_spin.value(),
                "screen_hash_interval": self.screen_hash_interval_spin.value(),
                "action_cooldown": self.action_cooldown_spin.value(),
                "auto_feature_action_cooldown": self.auto_feature_action_cooldown_spin.value(),
                "auto_feature_scan_interval": self.auto_feature_scan_interval_spin.value(),
                "check_game_open_interval_pc": float(self.check_game_open_interval_spin.value()),
                "login_timeout": self.login_timeout_spin.value(),
                "post_login_timeout": self.post_login_timeout_spin.value(),
                "in_game_confirm_timeout": self.in_game_confirm_timeout_spin.value(),
                "scheduled_restart_enabled": self.scheduled_restart_global_enable_check.isChecked()
                if hasattr(self, "scheduled_restart_global_enable_check") else False,
                "scheduled_restart_hours": int(self.scheduled_restart_hours_spin.value())
                if hasattr(self, "scheduled_restart_hours_spin") else 0,
                "scheduled_restart_minutes": int(self.scheduled_restart_minutes_spin.value())
                if hasattr(self, "scheduled_restart_minutes_spin") else 0,
            },
        }

        if hasattr(self, "device_feature_profile_checks"):
            profile_map = {}
            for device_id, widgets in self.device_feature_profile_checks.items():
                profile_map[device_id] = {
                    "auto_battle_enabled": widgets["auto_battle_enabled"].isChecked(),
                    "stop_on_low_energy": widgets["stop_on_low_energy"].isChecked(),
                    "disconnect_enabled": widgets["disconnect_enabled"].isChecked(),
                    "auto_enable_features_enabled": widgets["auto_enable_features_enabled"].isChecked(),
                    "scheduled_restart_enabled": widgets["scheduled_restart_enabled"].isChecked(),
                }
            config["device_feature_profiles"] = profile_map
            # 向後相容：沿用既有欄位作為每設備活力策略。
            config["device_configs"] = {
                device_id: values["stop_on_low_energy"]
                for device_id, values in profile_map.items()
            }

        return config

    # ── 啟動/停止 ──────────────────────────────────────────────
    def on_start_stop(self):
        if self.is_running:
            self.stop_bot()
        else:
            if self.config_dirty:
                self.append_log("[CONFIG] " + t("status_unsaved_block", "有未儲存設定，請先儲存或重置後再啟動"))
                self._update_run_action_guard()
                return
            if len(self.selected_windows) == 0:
                QMessageBox.warning(self, t("dialog_warning", "警告"), t("status_none_selected", "請至少選擇一個遊戲窗口"))
                return
            self.start_bot()

    def start_bot(self):
        from gui.pc_threads import BotControlThread
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
        self.window_list.setEnabled(False)
        self.status_label.setText(t("resumed", "執行中"))
        self.status_label.setStyleSheet("background-color: #4CAF50; color: white; padding: 8px; border-radius: 4px;")

        self.set_config_editing_enabled(False)

        config = self._build_config()
        self.bot_thread = BotControlThread(self.selected_windows, config)
        self.bot_thread.log_signal.connect(self.append_log)
        self.bot_thread.hwnd_changed_signal.connect(self.on_hwnd_changed)
        self.bot_thread.finished.connect(self.on_bot_finished)
        self.bot_thread.start()
        self.append_log(f"[START] PC 模式已啟動，控制 {len(self.selected_windows)} 個窗口")

    def stop_bot(self):
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
        self.window_list.setEnabled(True)
        self.status_label.setText(t("stopped", "已停止"))
        self.status_label.setStyleSheet("background-color: #FF6B6B; color: white; padding: 8px; border-radius: 4px;")
        self.set_config_editing_enabled(True)
        self.start_btn.setEnabled(len(self.selected_windows) > 0)
        self._update_run_action_guard()
        self.append_log("[STOP] 已停止")

    def on_bot_finished(self):
        if self.is_running:
            self.stop_bot()

    def on_hwnd_changed(self, old_hwnd, new_hwnd):
        for i, h in enumerate(self.selected_windows):
            if h == old_hwnd:
                self.selected_windows[i] = new_hwnd
                break

        title = self.window_map.pop(old_hwnd, "")
        if not title:
            try:
                import win32gui as _w32  # type: ignore[reportMissingImports]
                title = _w32.GetWindowText(new_hwnd) or ""
            except Exception:
                title = ""
        self.window_map[new_hwnd] = title

        from PyQt5.QtCore import Qt
        for i in range(self.window_list.count()):
            item = self.window_list.item(i)
            if item and item.data(Qt.UserRole) == old_hwnd:
                display = f"{title} (HWND: {new_hwnd})"
                item.setText(display)
                item.setData(Qt.UserRole, new_hwnd)
                break

        self.append_log(f"[DETECT] 視窗已更新: HWND {old_hwnd} → {new_hwnd}")

    # ── 暫停/除錯 ──────────────────────────────────────────────
    def on_pause(self):
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

    # ── 設定推送 ───────────────────────────────────────────────
    def _push_config_update(self):
        if not AUTOPVE_AVAILABLE:
            return
        try:
            cfg = self._build_config()
            rc = autoPVE.RUNNING_CONFIG
            if rc is None:
                return
            for key in ("wait_times", "disconnect"):
                if key in cfg:
                    rc.setdefault(key, {}).update(cfg[key])
            if "energy_strategy" in cfg:
                rc["energy_strategy"] = cfg["energy_strategy"]
            if "auto_battle_enabled" in cfg:
                rc["auto_battle_enabled"] = cfg["auto_battle_enabled"]
            if "device_configs" in cfg:
                rc["device_configs"] = dict(cfg["device_configs"])
            if "device_feature_profiles" in cfg:
                rc["device_feature_profiles"] = dict(cfg["device_feature_profiles"])
            if "thresholds" in cfg:
                for platform, values in cfg["thresholds"].items():
                    rc.setdefault("thresholds", {}).setdefault(platform, {}).update(values)
            if self.bot_thread and getattr(self.bot_thread, "bots", None):
                for bot in self.bot_thread.bots:
                    if hasattr(bot, "refresh_runtime_config"):
                        bot.refresh_runtime_config()
        except Exception:
            pass

    def browse_pc_exe(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            t("select_game_exe", "選擇遊戲執行檔"),
            "",
            t("file_filter_exe", "Executable (*.exe);;All Files (*)"),
        )
        if file_path:
            self.pc_exe_path_input.setText(file_path)

    # ── 設定編輯啟用狀態 ───────────────────────────────────────
    def set_config_editing_enabled(self, enabled):
        for spinner in self.wait_spinners.values():
            spinner.setEnabled(enabled)
        for spinner in self.threshold_spinners.values():
            spinner.setEnabled(enabled)
        self.auto_battle_enable_check.setEnabled(enabled)
        self.energy_check.setEnabled(enabled)
        self.disconnect_enable_check.setEnabled(enabled)
        self.same_screen_timeout_spin.setEnabled(enabled)
        self.pc_launch_wait_timeout_spin.setEnabled(enabled and not self.is_running)
        unlimited = self.max_reconnect_unlimited_check.isChecked()
        self.max_reconnect_attempts_spin.setEnabled(enabled and not unlimited)
        self.max_reconnect_unlimited_check.setEnabled(enabled)
        self.pc_exe_path_input.setEnabled(enabled)
        self.pc_exe_browse_btn.setEnabled(enabled)
        self.screen_hash_diff_threshold_spin.setEnabled(enabled)
        self.screen_hash_interval_spin.setEnabled(enabled)
        self.action_cooldown_spin.setEnabled(enabled)
        self.check_game_open_interval_spin.setEnabled(enabled and not self.is_running)
        if hasattr(self, "scheduled_restart_global_enable_check"):
            self.scheduled_restart_global_enable_check.setEnabled(enabled)
        if hasattr(self, "scheduled_restart_hours_spin"):
            self.scheduled_restart_hours_spin.setEnabled(enabled)
        if hasattr(self, "scheduled_restart_minutes_spin"):
            self.scheduled_restart_minutes_spin.setEnabled(enabled)
        self.auto_feature_action_cooldown_spin.setEnabled(enabled)
        self.login_timeout_spin.setEnabled(enabled)
        self.post_login_timeout_spin.setEnabled(enabled)
        self.restart_game_enable_check.setEnabled(enabled)
        self.login_game_enable_check.setEnabled(enabled)
        for key, spinner in self.disconnect_threshold_spinners.items():
            if key not in self.auto_feature_threshold_keys:
                spinner.setEnabled(enabled)
        if hasattr(self, "device_feature_profile_checks"):
            for widgets in self.device_feature_profile_checks.values():
                for cb in widgets.values():
                    cb.setEnabled(enabled)
        if hasattr(self, "batch_apply_btn"):
            self.batch_apply_btn.setEnabled(enabled)
        self.auto_enable_features_check.setEnabled(enabled)
        self._update_auto_features_tab_enabled(editing_enabled=enabled)
        if hasattr(self, "save_btn"):
            self.save_btn.setEnabled(enabled and self.config_dirty)
        if hasattr(self, "reset_btn"):
            self.reset_btn.setEnabled(enabled and self.config_dirty)
        if hasattr(self, "restore_btn"):
            self.restore_btn.setEnabled(enabled)
        if hasattr(self, "launch_save_btn"):
            self.launch_save_btn.setEnabled(enabled and self.config_dirty)
        if hasattr(self, "launch_reset_btn"):
            self.launch_reset_btn.setEnabled(enabled and self.config_dirty)
        if hasattr(self, "launch_restore_btn"):
            self.launch_restore_btn.setEnabled(enabled)

    def closeEvent(self, event):
        from PyQt5.QtCore import QSettings
        QSettings("WLREHelperBot", "PCWindow").setValue("geometry", self.saveGeometry())
        if self.bot_thread:
            self.bot_thread.stop()
            self.bot_thread.wait()
        event.accept()
