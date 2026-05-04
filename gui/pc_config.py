"""
gui/pc_config.py
PCConfigMixin - PC 模式設定讀寫 mixin
"""

import json
import os
from copy import deepcopy

from i18n import t

from gui.shared import resource_path, AUTOPVE_AVAILABLE
from gui.device_feature_shared import clear_layout_widgets, build_device_feature_row

if AUTOPVE_AVAILABLE:
    import autoPVE


class PCConfigMixin:
    """PC 模式設定讀寫 mixin"""

    def _get_active_scope(self):
        """取得目前作用範圍：啟動頁或設定子頁。"""
        if hasattr(self, "tabs") and self.tabs.currentIndex() == 0:
            return "launch"
        tab_index = self.config_subtabs.currentIndex() if hasattr(self, "config_subtabs") else 0
        return f"config_{tab_index}"

    def _apply_scope_to_persisted_config(self, config_data, current_snapshot, scope):
        """將目前範圍的值套用到準備寫入的設定物件。"""
        disconnect_data = config_data.setdefault("disconnect", {})
        current_disconnect = current_snapshot.get("disconnect", {})

        auto_battle_wait_keys = {
            "scan_interval", "after_click", "pop_window", "battle_unlock", "join_confirm", "wait_battle_check"
        }
        auto_battle_threshold_keys = {
            "battle_title", "btn_add", "btn_confirm", "btn_join", "in_battle", "energy_low", "energy_9"
        }
        auto_feature_threshold_keys = set(getattr(self, "auto_feature_threshold_keys", []))
        reconnect_threshold_keys = set(self.disconnect_threshold_spinners.keys()) - auto_feature_threshold_keys

        reconnect_disconnect_keys = {
            "enabled", "same_screen_timeout", "max_reconnect_attempts", "pc_launch_wait_timeout",
            "restart_game_enabled", "login_game_enabled", "screen_hash_diff_threshold",
            "screen_hash_interval", "action_cooldown", "check_game_open_interval_pc", "login_timeout", "post_login_timeout",
            "scheduled_restart_enabled", "scheduled_restart_hours", "scheduled_restart_minutes",
        }
        auto_feature_disconnect_keys = {
            "auto_enable_features_enabled", "auto_enable_wander", "auto_enable_ai",
            "auto_feature_action_cooldown", "auto_feature_scan_interval", "in_game_confirm_timeout",
        }

        if scope == "launch":
            disconnect_data["pc_exe_path"] = current_disconnect.get("pc_exe_path", "")
            return

        thresholds_root = config_data.setdefault("thresholds", {})
        thresholds_pc = thresholds_root.setdefault("PC", {})

        if scope == "config_0":
            wait_times = config_data.setdefault("wait_times", {})
            for key in auto_battle_wait_keys:
                if key in current_snapshot.get("wait_times", {}):
                    wait_times[key] = current_snapshot["wait_times"][key]
            for key in auto_battle_threshold_keys:
                if key in current_snapshot.get("thresholds_pc", {}):
                    thresholds_pc[key] = current_snapshot["thresholds_pc"][key]
            config_data["energy_strategy"] = current_snapshot.get("energy_strategy", config_data.get("energy_strategy", True))
            config_data["auto_battle_enabled"] = current_snapshot.get("auto_battle_enabled", config_data.get("auto_battle_enabled", True))
            return

        if scope == "config_1":
            for key in reconnect_threshold_keys:
                if key in current_snapshot.get("thresholds_pc", {}):
                    thresholds_pc[key] = current_snapshot["thresholds_pc"][key]
            for key in reconnect_disconnect_keys:
                if key in current_disconnect:
                    disconnect_data[key] = current_disconnect[key]
            return

        if scope == "config_2":
            for key in auto_feature_threshold_keys:
                if key in current_snapshot.get("thresholds_pc", {}):
                    thresholds_pc[key] = current_snapshot["thresholds_pc"][key]
            for key in auto_feature_disconnect_keys:
                if key in current_disconnect:
                    disconnect_data[key] = current_disconnect[key]
            config_data["device_feature_profiles"] = deepcopy(
                current_snapshot.get("device_feature_profiles", config_data.get("device_feature_profiles", {}))
            )

    def _update_baseline_by_scope(self, baseline, source, scope):
        """只更新指定範圍到 baseline，保留其他未儲存分頁差異。"""
        if not baseline:
            return deepcopy(source)

        auto_battle_wait_keys = {
            "scan_interval", "after_click", "pop_window", "battle_unlock", "join_confirm", "wait_battle_check"
        }
        auto_battle_threshold_keys = {
            "battle_title", "btn_add", "btn_confirm", "btn_join", "in_battle", "energy_low", "energy_9"
        }
        auto_feature_threshold_keys = set(getattr(self, "auto_feature_threshold_keys", []))
        reconnect_threshold_keys = set(self.disconnect_threshold_spinners.keys()) - auto_feature_threshold_keys

        reconnect_disconnect_keys = {
            "enabled", "same_screen_timeout", "max_reconnect_attempts", "pc_launch_wait_timeout",
            "restart_game_enabled", "login_game_enabled", "screen_hash_diff_threshold",
            "screen_hash_interval", "action_cooldown", "check_game_open_interval_pc", "login_timeout", "post_login_timeout",
            "scheduled_restart_enabled", "scheduled_restart_hours", "scheduled_restart_minutes",
        }
        auto_feature_disconnect_keys = {
            "auto_enable_features_enabled", "auto_enable_wander", "auto_enable_ai",
            "auto_feature_action_cooldown", "auto_feature_scan_interval", "in_game_confirm_timeout",
        }

        if scope == "launch":
            baseline.setdefault("disconnect", {})["pc_exe_path"] = source.get("disconnect", {}).get("pc_exe_path", "")
            return baseline

        if scope == "config_0":
            for key in auto_battle_wait_keys:
                if key in source.get("wait_times", {}):
                    baseline.setdefault("wait_times", {})[key] = source["wait_times"][key]
            for key in auto_battle_threshold_keys:
                if key in source.get("thresholds_pc", {}):
                    baseline.setdefault("thresholds_pc", {})[key] = source["thresholds_pc"][key]
            baseline["energy_strategy"] = source.get("energy_strategy", baseline.get("energy_strategy", True))
            baseline["auto_battle_enabled"] = source.get("auto_battle_enabled", baseline.get("auto_battle_enabled", True))
            return baseline

        if scope == "config_1":
            for key in reconnect_threshold_keys:
                if key in source.get("thresholds_pc", {}):
                    baseline.setdefault("thresholds_pc", {})[key] = source["thresholds_pc"][key]
            for key in reconnect_disconnect_keys:
                if key in source.get("disconnect", {}):
                    baseline.setdefault("disconnect", {})[key] = source["disconnect"][key]
            return baseline

        if scope == "config_2":
            for key in auto_feature_threshold_keys:
                if key in source.get("thresholds_pc", {}):
                    baseline.setdefault("thresholds_pc", {})[key] = source["thresholds_pc"][key]
            for key in auto_feature_disconnect_keys:
                if key in source.get("disconnect", {}):
                    baseline.setdefault("disconnect", {})[key] = source["disconnect"][key]
            baseline["device_feature_profiles"] = deepcopy(source.get("device_feature_profiles", {}))
        return baseline

    def _collect_current_config(self):
        """收集目前 UI 設定為標準字典。"""
        unlimited = self.max_reconnect_unlimited_check.isChecked()
        return {
            "wait_times": {k: s.value() for k, s in self.wait_spinners.items()},
            "energy_strategy": self.energy_check.isChecked(),
            "auto_battle_enabled": self.auto_battle_enable_check.isChecked(),
            "thresholds_pc": {
                **{k: s.value() for k, s in self.threshold_spinners.items()},
                **{k: s.value() for k, s in self.disconnect_threshold_spinners.items()},
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
            "device_feature_profiles": self._collect_device_feature_profiles(),
        }

    def _collect_device_feature_profiles(self):
        profiles = {}
        if not hasattr(self, "device_feature_profile_checks"):
            return profiles
        for device_id, widgets in self.device_feature_profile_checks.items():
            profiles[device_id] = {
                "auto_battle_enabled": widgets["auto_battle_enabled"].isChecked(),
                "stop_on_low_energy": widgets["stop_on_low_energy"].isChecked(),
                "disconnect_enabled": widgets["disconnect_enabled"].isChecked(),
                "auto_enable_features_enabled": widgets["auto_enable_features_enabled"].isChecked(),
                "scheduled_restart_enabled": widgets["scheduled_restart_enabled"].isChecked(),
            }
        return profiles

    def _load_default_config(self):
        """讀取預設配置，並另外保留純預設供「恢復預設」使用。"""
        fallback = {
            "wait_times": {
                "scan_interval": 1.0, "after_click": 0.1, "pop_window": 0.1,
                "battle_unlock": 1.0, "join_confirm": 0.1, "wait_battle_check": 30.0
            },
            "energy_strategy": True,
            "auto_battle_enabled": True,
            "thresholds": {
                "PC": {
                    "battle_title": 0.80, "btn_add": 0.80, "btn_confirm": 0.80,
                    "btn_join": 0.80, "in_battle": 0.80, "energy_low": 0.85, "energy_9": 0.95,
                    "select_character": 0.60, "btn_wander_on": 0.80, "btn_wander_off": 0.65
                }
            },
            "disconnect": {
                "enabled": True, "same_screen_timeout": 120.0, "max_reconnect_attempts": 5,
                "auto_feature_scan_interval": 1.0, "check_game_open_interval_pc": 60.0,
                "auto_feature_action_cooldown": 0.5,
                "pc_launch_wait_timeout": 60.0, "restart_game_enabled": True,
                "login_game_enabled": True, "auto_enable_features_enabled": True,
                "auto_enable_wander": True, "auto_enable_ai": True,
                "scheduled_restart_enabled": False, "scheduled_restart_hours": 0, "scheduled_restart_minutes": 0,
                "pc_exe_path": "", "emu_package_name": "",
                "action_cooldown": 0.5,
                "in_game_confirm_timeout": 60.0,
            },
            "device_feature_profiles": {},
        }
        base = fallback
        try:
            with open(resource_path("default_config_pc.json"), "r", encoding="utf-8") as f:
                base = json.load(f)
        except Exception:
            try:
                with open(resource_path("default_config.json"), "r", encoding="utf-8") as f:
                    base = json.load(f)
            except Exception:
                base = fallback

        # 保存純預設，供 restore_defaults 使用（不受 bot_config 覆蓋）。
        self._factory_defaults = deepcopy(base)

        # 讀取已儲存的使用者設定（僅供啟動時帶入目前值）
        try:
            with open("bot_config_pc.json", "r", encoding="utf-8") as f:
                saved = json.load(f)
            if "wait_times" in saved:
                base.setdefault("wait_times", {}).update(saved.get("wait_times", {}))
            if "thresholds" in saved and "PC" in saved.get("thresholds", {}):
                base.setdefault("thresholds", {}).setdefault("PC", {}).update(
                    saved.get("thresholds", {}).get("PC", {})
                )
            if "energy_strategy" in saved:
                base["energy_strategy"] = saved.get("energy_strategy", True)
            if "auto_battle_enabled" in saved:
                base["auto_battle_enabled"] = saved.get("auto_battle_enabled", True)
            if "disconnect" in saved:
                saved_disconnect = dict(saved.get("disconnect", {}))
                saved_disconnect.pop("server_click_point", None)
                base.setdefault("disconnect", {}).update(saved_disconnect)
            if "device_feature_profiles" in saved:
                base["device_feature_profiles"] = saved.get("device_feature_profiles", {})
        except Exception:
            pass

        return base

    def on_config_changed(self):
        """配置變更"""
        if getattr(self, "_is_initializing", False):
            self.config_dirty = False
            if hasattr(self, "save_btn"):
                self.save_btn.setEnabled(False)
            if hasattr(self, "reset_btn"):
                self.reset_btn.setEnabled(False)
            if hasattr(self, "launch_save_btn"):
                self.launch_save_btn.setEnabled(False)
            if hasattr(self, "launch_reset_btn"):
                self.launch_reset_btn.setEnabled(False)
            return

        self.config_dirty = True
        if hasattr(self, "save_btn"):
            self.save_btn.setEnabled(True)
        if hasattr(self, "reset_btn"):
            self.reset_btn.setEnabled(True)
        if hasattr(self, "launch_save_btn"):
            self.launch_save_btn.setEnabled(True)
        if hasattr(self, "launch_reset_btn"):
            self.launch_reset_btn.setEnabled(True)
        self.update_current_config_display()
        if hasattr(self, "_update_run_action_guard"):
            self._update_run_action_guard()

    def save_config(self):
        """保存目前頁籤設定到 bot_config_pc.json。"""
        try:
            config_path = "bot_config_pc.json"
            config_data = {}
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)

            current_snapshot = self._collect_current_config()
            scope = self._get_active_scope()
            self._apply_scope_to_persisted_config(config_data, current_snapshot, scope)

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

            baseline = deepcopy(getattr(self, "_original_config", {}) or {})
            self._original_config = self._update_baseline_by_scope(baseline, current_snapshot, scope)
            after = self._collect_current_config()
            self.config_dirty = (after != self._original_config)
            if hasattr(self, "save_btn"):
                self.save_btn.setEnabled(self.config_dirty)
            if hasattr(self, "reset_btn"):
                self.reset_btn.setEnabled(self.config_dirty)
            if hasattr(self, "launch_save_btn"):
                self.launch_save_btn.setEnabled(self.config_dirty)
            if hasattr(self, "launch_reset_btn"):
                self.launch_reset_btn.setEnabled(self.config_dirty)
            self._label_base_texts = {}
            self._checkbox_base_texts = {}
            if self.is_running:
                self._push_config_update()
            self.update_current_config_display()
            if hasattr(self, "_update_run_action_guard"):
                self._update_run_action_guard()
            self.append_log("[CONFIG] " + t("config_saved", "設定已保存"))
        except Exception as e:
            self.append_log(f"[ERROR] 保存設定失敗: {e}")

    def reset_changes(self):
        """重置變更：僅重置目前頁籤到載入/上次保存基準。"""
        baseline = deepcopy(getattr(self, "_original_config", {}) or {})
        if not baseline:
            return

        target = deepcopy(self._collect_current_config())
        scope = self._get_active_scope()

        auto_battle_wait_keys = {
            "scan_interval", "after_click", "pop_window", "battle_unlock", "join_confirm", "wait_battle_check"
        }
        auto_battle_threshold_keys = {
            "battle_title", "btn_add", "btn_confirm", "btn_join", "in_battle", "energy_low", "energy_9"
        }
        auto_feature_threshold_keys = set(getattr(self, "auto_feature_threshold_keys", []))
        reconnect_threshold_keys = set(self.disconnect_threshold_spinners.keys()) - auto_feature_threshold_keys

        reconnect_disconnect_keys = {
            "enabled", "same_screen_timeout", "max_reconnect_attempts", "pc_launch_wait_timeout",
            "restart_game_enabled", "login_game_enabled", "screen_hash_diff_threshold",
            "screen_hash_interval", "action_cooldown", "check_game_open_interval_pc", "login_timeout", "post_login_timeout",
            "scheduled_restart_enabled", "scheduled_restart_hours", "scheduled_restart_minutes",
        }
        auto_feature_disconnect_keys = {
            "auto_enable_features_enabled", "auto_enable_wander", "auto_enable_ai",
            "auto_feature_action_cooldown", "auto_feature_scan_interval", "in_game_confirm_timeout",
        }

        if scope == "launch":
            if "pc_exe_path" in baseline.get("disconnect", {}):
                target["disconnect"]["pc_exe_path"] = baseline["disconnect"]["pc_exe_path"]

        elif scope == "config_0":
            for key in auto_battle_wait_keys:
                if key in baseline.get("wait_times", {}):
                    target["wait_times"][key] = baseline["wait_times"][key]
            for key in auto_battle_threshold_keys:
                if key in baseline.get("thresholds_pc", {}):
                    target["thresholds_pc"][key] = baseline["thresholds_pc"][key]
            target["energy_strategy"] = bool(baseline.get("energy_strategy", target.get("energy_strategy", True)))
            target["auto_battle_enabled"] = bool(baseline.get("auto_battle_enabled", target.get("auto_battle_enabled", True)))

        elif scope == "config_1":
            for key in reconnect_threshold_keys:
                if key in baseline.get("thresholds_pc", {}):
                    target["thresholds_pc"][key] = baseline["thresholds_pc"][key]
            for key in reconnect_disconnect_keys:
                if key in baseline.get("disconnect", {}):
                    target["disconnect"][key] = baseline["disconnect"][key]

        elif scope == "config_2":
            for key in auto_feature_threshold_keys:
                if key in baseline.get("thresholds_pc", {}):
                    target["thresholds_pc"][key] = baseline["thresholds_pc"][key]
            for key in auto_feature_disconnect_keys:
                if key in baseline.get("disconnect", {}):
                    target["disconnect"][key] = baseline["disconnect"][key]
            target["device_feature_profiles"] = deepcopy(baseline.get("device_feature_profiles", {}))

        self._apply_snapshot_to_ui(target)

        after = self._collect_current_config()
        self.config_dirty = (after != baseline)
        if hasattr(self, "save_btn"):
            self.save_btn.setEnabled(self.config_dirty)
        if hasattr(self, "reset_btn"):
            self.reset_btn.setEnabled(self.config_dirty)
        if hasattr(self, "launch_save_btn"):
            self.launch_save_btn.setEnabled(self.config_dirty)
        if hasattr(self, "launch_reset_btn"):
            self.launch_reset_btn.setEnabled(self.config_dirty)
        self.update_current_config_display()
        if hasattr(self, "_update_run_action_guard"):
            self._update_run_action_guard()
        self.append_log("[CONFIG] " + t("btn_reset_changes", "已重置變更"))

    def _apply_snapshot_to_ui(self, snapshot):
        """將設定快照套用到 UI 控件。"""
        wait_cfg = snapshot.get("wait_times", {})
        for key, spinner in self.wait_spinners.items():
            spinner.setValue(wait_cfg.get(key, spinner.value()))

        thr_cfg = snapshot.get("thresholds_pc", {})
        for key, spinner in self.threshold_spinners.items():
            spinner.setValue(thr_cfg.get(key, spinner.value()))
        for key, spinner in self.disconnect_threshold_spinners.items():
            spinner.setValue(thr_cfg.get(key, spinner.value()))

        self.energy_check.setChecked(bool(snapshot.get("energy_strategy", self.energy_check.isChecked())))
        self.auto_battle_enable_check.setChecked(bool(snapshot.get("auto_battle_enabled", self.auto_battle_enable_check.isChecked())))

        disconnect = snapshot.get("disconnect", {})
        self.disconnect_enable_check.setChecked(bool(disconnect.get("enabled", self.disconnect_enable_check.isChecked())))
        self.same_screen_timeout_spin.setValue(float(disconnect.get("same_screen_timeout", self.same_screen_timeout_spin.value())))
        attempts = int(disconnect.get("max_reconnect_attempts", 5))
        self.max_reconnect_unlimited_check.setChecked(attempts == 0)
        self.max_reconnect_attempts_spin.setValue(max(1, attempts) if attempts != 0 else 5)
        self.pc_launch_wait_timeout_spin.setValue(float(disconnect.get("pc_launch_wait_timeout", self.pc_launch_wait_timeout_spin.value())))
        self.restart_game_enable_check.setChecked(bool(disconnect.get("restart_game_enabled", self.restart_game_enable_check.isChecked())))
        self.login_game_enable_check.setChecked(bool(disconnect.get("login_game_enabled", self.login_game_enable_check.isChecked())))
        self.auto_enable_features_check.setChecked(bool(disconnect.get("auto_enable_features_enabled", self.auto_enable_features_check.isChecked())))
        self.auto_enable_wander_check.setChecked(bool(disconnect.get("auto_enable_wander", self.auto_enable_wander_check.isChecked())))
        self.auto_enable_ai_check.setChecked(bool(disconnect.get("auto_enable_ai", self.auto_enable_ai_check.isChecked())))
        self.pc_exe_path_input.setText(str(disconnect.get("pc_exe_path", self.pc_exe_path_input.text())))
        self.screen_hash_diff_threshold_spin.setValue(float(disconnect.get("screen_hash_diff_threshold", self.screen_hash_diff_threshold_spin.value())))
        self.screen_hash_interval_spin.setValue(float(disconnect.get("screen_hash_interval", self.screen_hash_interval_spin.value())))
        self.action_cooldown_spin.setValue(float(disconnect.get("action_cooldown", self.action_cooldown_spin.value())))
        self.auto_feature_action_cooldown_spin.setValue(float(disconnect.get("auto_feature_action_cooldown", self.auto_feature_action_cooldown_spin.value())))
        self.auto_feature_scan_interval_spin.setValue(float(disconnect.get("auto_feature_scan_interval", self.auto_feature_scan_interval_spin.value())))
        self.check_game_open_interval_spin.setValue(int(disconnect.get("check_game_open_interval_pc", self.check_game_open_interval_spin.value())))
        self.login_timeout_spin.setValue(float(disconnect.get("login_timeout", self.login_timeout_spin.value())))
        self.post_login_timeout_spin.setValue(float(disconnect.get("post_login_timeout", self.post_login_timeout_spin.value())))
        self.in_game_confirm_timeout_spin.setValue(float(disconnect.get("in_game_confirm_timeout", self.in_game_confirm_timeout_spin.value())))
        if hasattr(self, "scheduled_restart_global_enable_check"):
            self.scheduled_restart_global_enable_check.setChecked(bool(disconnect.get("scheduled_restart_enabled", False)))
        if hasattr(self, "scheduled_restart_hours_spin"):
            self.scheduled_restart_hours_spin.setValue(int(disconnect.get("scheduled_restart_hours", 0)))
        if hasattr(self, "scheduled_restart_minutes_spin"):
            self.scheduled_restart_minutes_spin.setValue(int(disconnect.get("scheduled_restart_minutes", 0)))
        if hasattr(self, "update_device_feature_profile_settings"):
            self._cached_device_feature_profiles = deepcopy(snapshot.get("device_feature_profiles", {}))
            self.update_device_feature_profile_settings()

    def restore_defaults(self):
        """恢復預設：僅套用目前頁籤。"""
        before = deepcopy(self._collect_current_config())
        target = deepcopy(before)
        defaults = deepcopy(getattr(self, "_factory_defaults", self.default_config or {}))
        scope = self._get_active_scope()

        auto_battle_wait_keys = {
            "scan_interval", "after_click", "pop_window", "battle_unlock", "join_confirm", "wait_battle_check"
        }
        auto_battle_threshold_keys = {
            "battle_title", "btn_add", "btn_confirm", "btn_join", "in_battle", "energy_low", "energy_9"
        }
        auto_feature_threshold_keys = set(getattr(self, "auto_feature_threshold_keys", []))
        reconnect_threshold_keys = set(self.disconnect_threshold_spinners.keys()) - auto_feature_threshold_keys

        reconnect_disconnect_keys = {
            "enabled", "same_screen_timeout", "max_reconnect_attempts", "pc_launch_wait_timeout",
            "restart_game_enabled", "login_game_enabled", "screen_hash_diff_threshold",
            "screen_hash_interval", "action_cooldown", "check_game_open_interval_pc", "login_timeout", "post_login_timeout",
            "scheduled_restart_enabled", "scheduled_restart_hours", "scheduled_restart_minutes",
        }
        auto_feature_disconnect_keys = {
            "auto_enable_features_enabled", "auto_enable_wander", "auto_enable_ai",
            "auto_feature_action_cooldown", "auto_feature_scan_interval", "in_game_confirm_timeout",
        }

        default_wait = defaults.get("wait_times", {})
        for key in target.get("wait_times", {}):
            if scope == "config_0" and key in auto_battle_wait_keys and key in default_wait:
                target["wait_times"][key] = default_wait[key]

        default_thresholds = defaults.get("thresholds", {}).get("PC", {})
        for key in target.get("thresholds_pc", {}):
            if key not in default_thresholds:
                continue
            if scope == "config_0" and key in auto_battle_threshold_keys:
                target["thresholds_pc"][key] = default_thresholds[key]
            elif scope == "config_1" and key in reconnect_threshold_keys:
                target["thresholds_pc"][key] = default_thresholds[key]
            elif scope == "config_2" and key in auto_feature_threshold_keys:
                target["thresholds_pc"][key] = default_thresholds[key]

        if scope == "config_0":
            if "energy_strategy" in defaults:
                target["energy_strategy"] = defaults.get("energy_strategy", True)
            if "auto_battle_enabled" in defaults:
                target["auto_battle_enabled"] = defaults.get("auto_battle_enabled", True)

        disconnect_defaults = defaults.get("disconnect", {})
        if scope == "launch":
            target.setdefault("disconnect", {})["pc_exe_path"] = disconnect_defaults.get("pc_exe_path", "")
        for key in list(target.get("disconnect", {}).keys()):
            if key not in disconnect_defaults:
                continue
            if scope == "config_1" and key in reconnect_disconnect_keys:
                target["disconnect"][key] = disconnect_defaults[key]
            elif scope == "config_2" and key in auto_feature_disconnect_keys:
                target["disconnect"][key] = disconnect_defaults[key]

        if scope == "config_2":
            target["device_feature_profiles"] = {}

        self._apply_snapshot_to_ui(target)

        after = self._collect_current_config()
        baseline = deepcopy(getattr(self, "_original_config", {}) or {})
        self.config_dirty = (after != baseline)
        if hasattr(self, "save_btn"):
            self.save_btn.setEnabled(self.config_dirty)
        if hasattr(self, "reset_btn"):
            self.reset_btn.setEnabled(self.config_dirty)
        if hasattr(self, "launch_save_btn"):
            self.launch_save_btn.setEnabled(self.config_dirty)
        if hasattr(self, "launch_reset_btn"):
            self.launch_reset_btn.setEnabled(self.config_dirty)
        self.update_current_config_display()
        if hasattr(self, "_update_run_action_guard"):
            self._update_run_action_guard()
        self.append_log("[CONFIG] " + t("btn_restore_defaults", "已恢復預設設定"))

    def _default_device_feature_profile(self):
        return {
            "auto_battle_enabled": bool(self.auto_battle_enable_check.isChecked()),
            "stop_on_low_energy": bool(self.energy_check.isChecked()),
            "disconnect_enabled": bool(self.disconnect_enable_check.isChecked()),
            "auto_enable_features_enabled": bool(self.auto_enable_features_check.isChecked()),
            "scheduled_restart_enabled": bool(
                self.scheduled_restart_global_enable_check.isChecked()
                if hasattr(self, "scheduled_restart_global_enable_check") else False
            ),
        }

    def _selected_pc_device_ids(self):
        return [f"PC-{int(hwnd)}" for hwnd in getattr(self, "selected_windows", [])]

    def update_device_feature_profile_settings(self):
        if not hasattr(self, "device_feature_profile_container_layout"):
            return
        clear_layout_widgets(self.device_feature_profile_container_layout)
        self.device_feature_profile_checks = {}

        selected_ids = self._selected_pc_device_ids()
        if not selected_ids:
            from PyQt5.QtWidgets import QLabel
            empty_label = QLabel(t("device_feature_empty", "尚未選擇任何設備。請先在「啟動」頁選擇設備。"))
            self.device_feature_profile_container_layout.addWidget(empty_label)
            return

        defaults = self._default_device_feature_profile()
        snapshot_profiles = getattr(self, "_cached_device_feature_profiles", None)
        if snapshot_profiles is None:
            snapshot_profiles = self._collect_current_config().get("device_feature_profiles", {})

        for device_id in selected_ids:
            hwnd = int(device_id.split("-")[-1])
            title = self.window_map.get(hwnd, device_id)
            profile = dict(defaults)
            profile.update(snapshot_profiles.get(device_id, {}))
            row, widgets = build_device_feature_row(title, profile, self.on_config_changed, t)
            self.device_feature_profile_container_layout.addWidget(row)
            self.device_feature_profile_checks[device_id] = widgets

    def apply_batch_device_feature_profile(self):
        if not hasattr(self, "device_feature_profile_checks"):
            return
        batch = {
            "auto_battle_enabled": self.batch_auto_battle_check.isChecked(),
            "stop_on_low_energy": self.batch_stop_on_low_energy_check.isChecked(),
            "disconnect_enabled": self.batch_disconnect_check.isChecked(),
            "auto_enable_features_enabled": self.batch_auto_features_check.isChecked(),
            "scheduled_restart_enabled": self.batch_scheduled_restart_check.isChecked(),
        }
        for widgets in self.device_feature_profile_checks.values():
            for key, val in batch.items():
                widgets[key].setChecked(bool(val))
        self.on_config_changed()
