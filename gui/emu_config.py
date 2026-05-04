"""
gui/emu_config.py
EmuConfigMixin - EMU 模式設定載入/儲存/還原 mixin
"""

import json
import os
from copy import deepcopy

from i18n import t

from gui.shared import resource_path, AUTOPVE_AVAILABLE, autoPVE
from gui.device_feature_shared import clear_layout_widgets, build_device_feature_row


class EmuConfigMixin:
    """EMU 模式設定 mixin：讀寫設定檔、套用至 UI、還原預設"""

    def _get_active_scope(self):
        """取得目前作用範圍：啟動頁或設定子頁。"""
        if hasattr(self, "tabs") and self.tabs.currentIndex() == 0:
            return "launch"
        tab_index = self.config_subtabs.currentIndex() if hasattr(self, "config_subtabs") else 0
        return f"config_{tab_index}"

    def _update_baseline_by_scope(self, baseline, source, scope):
        """只更新 baseline 的指定範圍。"""
        if not baseline:
            return deepcopy(source)

        auto_feature_threshold_keys = set(getattr(self, "auto_feature_threshold_keys", []))
        reconnect_threshold_keys = {
            "disconnect_hint", "btn_reconnect", "btn_back_to_login", "login_from_other_place",
            "multi_login", "custom_login", "btn_login_account", "select_server", "select_character",
            "login_game_button", "start_game_announcement", "announcement", "update_resource",
            "pop_gift_box", "dont_ask_today", "btn_cross", "btn_power_saving",
        }

        if scope == "launch":
            baseline.setdefault("disconnect", {})["emu_package_name"] = source.get("disconnect", {}).get("emu_package_name", "")
            baseline["emulator_paths"] = deepcopy(source.get("emulator_paths", {}))
            return baseline

        if scope == "config_0":
            baseline["wait_times"] = deepcopy(source.get("wait_times", {}))
            for key in ("battle_title", "btn_add", "btn_confirm", "btn_join", "in_battle", "energy_low", "energy_9"):
                if key in source.get("thresholds_emu", {}):
                    baseline.setdefault("thresholds_emu", {})[key] = source["thresholds_emu"][key]
            baseline["energy_strategy"] = source.get("energy_strategy", baseline.get("energy_strategy", True))
            baseline["auto_battle_enabled"] = source.get("auto_battle_enabled", baseline.get("auto_battle_enabled", True))
            baseline["device_strategies"] = deepcopy(source.get("device_strategies", {}))
            return baseline

        if scope == "config_1":
            for key in reconnect_threshold_keys:
                if key in source.get("thresholds_emu", {}):
                    baseline.setdefault("thresholds_emu", {})[key] = source["thresholds_emu"][key]
            for key in (
                "enabled", "same_screen_timeout", "max_reconnect_attempts", "pc_launch_wait_timeout",
                "restart_game_enabled", "login_game_enabled", "emu_package_name", "screen_hash_diff_threshold",
                "screen_hash_interval", "action_cooldown", "check_game_open_interval_emu", "login_timeout", "post_login_timeout",
                "scheduled_restart_enabled", "scheduled_restart_hours", "scheduled_restart_minutes",
            ):
                if key in source.get("disconnect", {}):
                    baseline.setdefault("disconnect", {})[key] = source["disconnect"][key]
            return baseline

        if scope == "config_2":
            for key in auto_feature_threshold_keys:
                if key in source.get("thresholds_emu", {}):
                    baseline.setdefault("thresholds_emu", {})[key] = source["thresholds_emu"][key]
            for key in (
                "auto_enable_features_enabled", "auto_enable_wander", "auto_enable_ai",
                "auto_feature_action_cooldown", "auto_feature_scan_interval", "in_game_confirm_timeout",
            ):
                if key in source.get("disconnect", {}):
                    baseline.setdefault("disconnect", {})[key] = source["disconnect"][key]
            baseline["device_auto_features"] = deepcopy(source.get("device_auto_features", {}))
            baseline["device_feature_profiles"] = deepcopy(source.get("device_feature_profiles", {}))
        return baseline

    def _load_default_config(self):
        """讀取預設配置"""
        fallback = {
            "wait_times": {
                "scan_interval": 1.0, "after_click": 0.1, "pop_window": 0.1,
                "battle_unlock": 1.0, "join_confirm": 0.1, "wait_battle_check": 30.0
            },
            "energy_strategy": True,
            "thresholds": {
                "EMU": {
                    "battle_title": 0.70, "btn_add": 0.70, "btn_confirm": 0.70,
                    "btn_join": 0.70, "in_battle": 0.70, "energy_low": 0.74, "energy_9": 0.95,
                    "disconnect_hint": 0.70, "btn_reconnect": 0.70, "btn_back_to_login": 0.70,
                    "multi_login": 0.70, "custom_login": 0.70,
                    "btn_login_account": 0.70, "select_server": 0.70, "select_character": 0.70,
                    "login_game_button": 0.70, "pop_gift_box": 0.70, "start_game_announcement": 0.70,
                    "announcement": 0.70, "dont_ask_today": 0.70,
                    "btn_cross": 0.70, "btn_power_saving": 0.70,
                    "btn_wander_on": 0.70, "btn_wander_off": 0.70,
                    "btn_ai": 0.70, "btn_ai_off_in_battle": 0.70,
                }
            },
            "disconnect": {
                "enabled": True,
                "same_screen_timeout": 45.0,
                "max_reconnect_attempts": 5,
                "pc_launch_wait_timeout": 25.0,
                "scheduled_restart_enabled": False,
                "scheduled_restart_hours": 0,
                "scheduled_restart_minutes": 0,
                "restart_game_enabled": True,
                "login_game_enabled": True,
                "auto_enable_features_enabled": True,
                "auto_enable_wander": True,
                "auto_enable_ai": True,
                "pc_exe_path": "",
                "emu_package_name": "",
            },
            "device_feature_profiles": {},
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
            config_path = "bot_config_emu.json"
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                if "wait_times" in config_data:
                    self.current_config["wait_times"].update(config_data["wait_times"])
                if "energy_strategy" in config_data:
                    self.current_config["energy_strategy"] = config_data["energy_strategy"]
                if "auto_battle_enabled" in config_data:
                    self.current_config["auto_battle_enabled"] = config_data["auto_battle_enabled"]
                if "device_strategies" in config_data:
                    self.current_config["device_strategies"] = config_data["device_strategies"]
                if "device_auto_features" in config_data:
                    self.current_config["device_auto_features"] = config_data["device_auto_features"]
                if "device_feature_profiles" in config_data:
                    self.current_config["device_feature_profiles"] = config_data["device_feature_profiles"]
                if "thresholds" in config_data and "EMU" in config_data["thresholds"]:
                    self.current_config["thresholds_emu"].update(config_data["thresholds"]["EMU"])
                if "disconnect" in config_data:
                    disconnect_cfg = dict(config_data["disconnect"])
                    disconnect_cfg.pop("server_click_point", None)
                    self.current_config["disconnect"].update(disconnect_cfg)
                if "emulator_paths" in config_data:
                    self.current_config["emulator_paths"] = config_data["emulator_paths"]
        except Exception as e:
            print(f"[WARN] 加載配置失敗: {e}")

    def _save_config(self):
        """保存配置"""
        try:
            config_path = "bot_config_emu.json"
            config_data = {}
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)

            config_data["wait_times"] = self.current_config["wait_times"]
            config_data["energy_strategy"] = self.current_config["energy_strategy"]
            config_data["auto_battle_enabled"] = self.current_config["auto_battle_enabled"]
            config_data["device_strategies"] = self.current_config["device_strategies"]
            config_data["device_auto_features"] = self.current_config["device_auto_features"]
            config_data["device_feature_profiles"] = self.current_config.get("device_feature_profiles", {})

            if "thresholds" not in config_data:
                config_data["thresholds"] = {}
            config_data["thresholds"]["EMU"] = self.current_config["thresholds_emu"]
            disconnect_cfg = dict(self.current_config["disconnect"])
            disconnect_cfg.pop("server_click_point", None)
            config_data["disconnect"] = disconnect_cfg

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
        """將載入的配置套用到 UI 控件，並將 LDPlayer 路徑注入核心偵測"""
        emu_paths = self.current_config.get("emulator_paths", {})
        for key, path in emu_paths.items():
            if key in self.emulator_path_inputs:
                self.emulator_path_inputs[key].setText(path)
        ld_path = emu_paths.get("ldplayer", "")
        if ld_path and AUTOPVE_AVAILABLE:
            self._inject_ldplayer_path(ld_path)

    def _inject_ldplayer_path(self, ld_dir):
        """將使用者設定的 LDPlayer 路徑注入到核心偵測"""
        try:
            from core.device_utils import LDPLAYER_CONSOLE_CACHE
            for exe in ["ldconsole.exe", "dnconsole.exe"]:
                path = os.path.join(ld_dir, exe)
                if os.path.isfile(path):
                    LDPLAYER_CONSOLE_CACHE["path"] = path
                    LDPLAYER_CONSOLE_CACHE["instances"] = None  # 強制重新讀取
                    LDPLAYER_CONSOLE_CACHE["ts"] = 0.0
                    break
        except Exception:
            pass

    def on_config_changed(self):
        """配置變更"""
        # 更新 current_config
        for key, spinner in self.threshold_spinners.items():
            self.current_config["thresholds_emu"][key] = spinner.value()

        for key, spinner in self.wait_spinners.items():
            self.current_config["wait_times"][key] = spinner.value()

        self.current_config["energy_strategy"] = self.energy_check.isChecked()
        self.current_config["auto_battle_enabled"] = self.auto_battle_enable_check.isChecked()

        unlimited = self.max_reconnect_unlimited_check.isChecked()
        self.current_config["disconnect"]["enabled"] = self.disconnect_enable_check.isChecked()
        self.current_config["disconnect"]["same_screen_timeout"] = self.same_screen_timeout_spin.value()
        self.current_config["disconnect"]["max_reconnect_attempts"] = 0 if unlimited else int(
            self.max_reconnect_attempts_spin.value()
        )
        self.current_config["disconnect"]["pc_launch_wait_timeout"] = self.pc_launch_wait_timeout_spin.value()
        self.current_config["disconnect"]["restart_game_enabled"] = self.restart_game_enable_check.isChecked()
        self.current_config["disconnect"]["login_game_enabled"] = self.login_game_enable_check.isChecked()
        self.current_config["disconnect"]["auto_enable_features_enabled"] = self.auto_enable_features_check.isChecked()
        self.current_config["disconnect"]["auto_enable_wander"] = self.auto_enable_wander_check.isChecked()
        self.current_config["disconnect"]["auto_enable_ai"] = self.auto_enable_ai_check.isChecked()
        self.current_config["disconnect"]["emu_package_name"] = self.emu_package_input.text().strip()
        self.current_config["disconnect"]["screen_hash_diff_threshold"] = self.screen_hash_diff_threshold_spin.value()
        self.current_config["disconnect"]["screen_hash_interval"] = self.screen_hash_interval_spin.value()
        self.current_config["disconnect"]["action_cooldown"] = self.action_cooldown_spin.value()
        self.current_config["disconnect"]["auto_feature_action_cooldown"] = self.auto_feature_action_cooldown_spin.value()
        self.current_config["disconnect"]["auto_feature_scan_interval"] = self.auto_feature_scan_interval_spin.value()
        self.current_config["disconnect"]["check_game_open_interval_emu"] = float(self.check_game_open_interval_spin.value())
        self.current_config["disconnect"]["login_timeout"] = self.login_timeout_spin.value()
        self.current_config["disconnect"]["post_login_timeout"] = self.post_login_timeout_spin.value()
        self.current_config["disconnect"]["in_game_confirm_timeout"] = self.in_game_confirm_timeout_spin.value()
        if hasattr(self, "scheduled_restart_hours_spin"):
            self.current_config["disconnect"]["scheduled_restart_hours"] = int(self.scheduled_restart_hours_spin.value())
        if hasattr(self, "scheduled_restart_minutes_spin"):
            self.current_config["disconnect"]["scheduled_restart_minutes"] = int(self.scheduled_restart_minutes_spin.value())
        if hasattr(self, "scheduled_restart_global_enable_check"):
            self.current_config["disconnect"]["scheduled_restart_enabled"] = self.scheduled_restart_global_enable_check.isChecked()

        emu_paths = {}
        for key, path_input in self.emulator_path_inputs.items():
            path = path_input.text().strip()
            if path:
                emu_paths[key] = path
        self.current_config["emulator_paths"] = emu_paths

        for key, spinner in self.disconnect_threshold_spinners.items():
            self.current_config["thresholds_emu"][key] = spinner.value()

        for serial, check in self.device_energy_checks.items():
            self.current_config["device_strategies"][serial] = check.isChecked()

        for serial, widgets in self.device_auto_feature_checks.items():
            self.current_config["device_auto_features"][serial] = {
                "wander": widgets["wander"].isChecked(),
                "ai": widgets["ai"].isChecked(),
            }

        if hasattr(self, "device_feature_profile_checks"):
            self.current_config.setdefault("device_feature_profiles", {})
            for serial, widgets in self.device_feature_profile_checks.items():
                self.current_config["device_feature_profiles"][serial] = {
                    "auto_battle_enabled": widgets["auto_battle_enabled"].isChecked(),
                    "stop_on_low_energy": widgets["stop_on_low_energy"].isChecked(),
                    "disconnect_enabled": widgets["disconnect_enabled"].isChecked(),
                    "auto_enable_features_enabled": widgets["auto_enable_features_enabled"].isChecked(),
                    "scheduled_restart_enabled": widgets["scheduled_restart_enabled"].isChecked(),
                }

        self.update_current_config_display()

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
        self.save_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)
        if hasattr(self, "launch_save_btn"):
            self.launch_save_btn.setEnabled(True)
        if hasattr(self, "launch_reset_btn"):
            self.launch_reset_btn.setEnabled(True)
        self._update_run_action_guard()

    def save_config(self):
        """保存目前頁籤設定。"""
        self.on_config_changed()

        scope = self._get_active_scope()
        try:
            config_path = "bot_config_emu.json"
            config_data = {}
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)

            if scope == "launch":
                config_data.setdefault("disconnect", {})["emu_package_name"] = self.current_config.get("disconnect", {}).get("emu_package_name", "")
                config_data["emulator_paths"] = deepcopy(self.current_config.get("emulator_paths", {}))
            elif scope == "config_0":
                config_data["wait_times"] = deepcopy(self.current_config.get("wait_times", {}))
                config_data["energy_strategy"] = self.current_config.get("energy_strategy", True)
                config_data["auto_battle_enabled"] = self.current_config.get("auto_battle_enabled", True)
                config_data["device_strategies"] = deepcopy(self.current_config.get("device_strategies", {}))
                config_data.setdefault("thresholds", {}).setdefault("EMU", {})
                for key in ("battle_title", "btn_add", "btn_confirm", "btn_join", "in_battle", "energy_low", "energy_9"):
                    if key in self.current_config.get("thresholds_emu", {}):
                        config_data["thresholds"]["EMU"][key] = self.current_config["thresholds_emu"][key]
            elif scope == "config_1":
                config_data.setdefault("thresholds", {}).setdefault("EMU", {})
                for key in (
                    "disconnect_hint", "btn_reconnect", "btn_back_to_login", "login_from_other_place",
                    "multi_login", "custom_login", "btn_login_account", "select_server", "select_character",
                    "login_game_button", "start_game_announcement", "announcement", "update_resource",
                    "pop_gift_box", "dont_ask_today", "btn_cross", "btn_power_saving",
                ):
                    if key in self.current_config.get("thresholds_emu", {}):
                        config_data["thresholds"]["EMU"][key] = self.current_config["thresholds_emu"][key]
                config_data.setdefault("disconnect", {})
                for key in (
                    "enabled", "same_screen_timeout", "max_reconnect_attempts", "pc_launch_wait_timeout",
                    "restart_game_enabled", "login_game_enabled", "emu_package_name", "screen_hash_diff_threshold",
                    "screen_hash_interval", "action_cooldown", "check_game_open_interval_emu", "login_timeout", "post_login_timeout",
                    "scheduled_restart_enabled", "scheduled_restart_hours", "scheduled_restart_minutes",
                ):
                    if key in self.current_config.get("disconnect", {}):
                        config_data["disconnect"][key] = self.current_config["disconnect"][key]
            else:
                config_data.setdefault("thresholds", {}).setdefault("EMU", {})
                for key in getattr(self, "auto_feature_threshold_keys", []):
                    if key in self.current_config.get("thresholds_emu", {}):
                        config_data["thresholds"]["EMU"][key] = self.current_config["thresholds_emu"][key]
                config_data.setdefault("disconnect", {})
                for key in (
                    "auto_enable_features_enabled", "auto_enable_wander", "auto_enable_ai",
                    "auto_feature_action_cooldown", "auto_feature_scan_interval", "in_game_confirm_timeout",
                ):
                    if key in self.current_config.get("disconnect", {}):
                        config_data["disconnect"][key] = self.current_config["disconnect"][key]
                config_data["device_auto_features"] = deepcopy(self.current_config.get("device_auto_features", {}))
                config_data["device_feature_profiles"] = deepcopy(self.current_config.get("device_feature_profiles", {}))

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            self.append_log("[CONFIG] " + t("config_saved", "設定已保存"))
        except Exception as e:
            self.append_log(f"[ERROR] 保存設定失敗: {e}")
            return

        baseline = deepcopy(getattr(self, "_original_config", {}) or {})
        self._original_config = self._update_baseline_by_scope(baseline, self.current_config, scope)
        self._label_base_texts = {}
        self._checkbox_base_texts = {}
        self.update_current_config_display()
        self.config_dirty = (self.current_config != self._original_config)
        self.save_btn.setEnabled(self.config_dirty)
        self.reset_btn.setEnabled(self.config_dirty)
        if hasattr(self, "launch_save_btn"):
            self.launch_save_btn.setEnabled(self.config_dirty)
        if hasattr(self, "launch_reset_btn"):
            self.launch_reset_btn.setEnabled(self.config_dirty)
        if self.is_running:
            self._push_config_update()
        self._update_run_action_guard()

    def reset_changes(self):
        """重置變更：僅重置目前選中頁籤到上次保存/載入基準。"""
        baseline = deepcopy(self._original_config)
        target = deepcopy(self.current_config)
        scope = self._get_active_scope()

        auto_battle_wait_keys = {
            "scan_interval", "after_click", "pop_window", "battle_unlock", "join_confirm", "wait_battle_check"
        }
        auto_battle_threshold_keys = {
            "battle_title", "btn_add", "btn_confirm", "btn_join", "in_battle", "energy_low", "energy_9"
        }
        auto_feature_threshold_keys = set(getattr(self, "auto_feature_threshold_keys", []))
        reconnect_threshold_keys = {
            "disconnect_hint", "btn_reconnect", "btn_back_to_login", "login_from_other_place",
            "multi_login", "custom_login", "btn_login_account", "select_server", "select_character",
            "login_game_button", "start_game_announcement", "announcement", "update_resource",
            "pop_gift_box", "dont_ask_today", "btn_cross", "btn_power_saving",
        }

        reconnect_disconnect_keys = {
            "enabled", "same_screen_timeout", "max_reconnect_attempts", "pc_launch_wait_timeout",
            "restart_game_enabled", "login_game_enabled", "emu_package_name", "screen_hash_diff_threshold",
            "screen_hash_interval", "action_cooldown", "check_game_open_interval_emu", "login_timeout", "post_login_timeout",
            "scheduled_restart_enabled", "scheduled_restart_hours", "scheduled_restart_minutes",
        }
        auto_feature_disconnect_keys = {
            "auto_enable_features_enabled", "auto_enable_wander", "auto_enable_ai",
            "auto_feature_action_cooldown", "auto_feature_scan_interval", "in_game_confirm_timeout",
        }

        if scope == "launch":
            target.setdefault("disconnect", {})["emu_package_name"] = baseline.get("disconnect", {}).get("emu_package_name", "")
            target["emulator_paths"] = deepcopy(baseline.get("emulator_paths", {}))

        elif scope == "config_0":
            for key in auto_battle_wait_keys:
                if key in baseline.get("wait_times", {}):
                    target.setdefault("wait_times", {})[key] = baseline["wait_times"][key]
            for key in auto_battle_threshold_keys:
                if key in baseline.get("thresholds_emu", {}):
                    target.setdefault("thresholds_emu", {})[key] = baseline["thresholds_emu"][key]
            target["energy_strategy"] = bool(baseline.get("energy_strategy", target.get("energy_strategy", True)))
            target["auto_battle_enabled"] = bool(baseline.get("auto_battle_enabled", target.get("auto_battle_enabled", True)))
            target["device_strategies"] = deepcopy(baseline.get("device_strategies", {}))

        elif scope == "config_1":
            for key in reconnect_threshold_keys:
                if key in baseline.get("thresholds_emu", {}):
                    target.setdefault("thresholds_emu", {})[key] = baseline["thresholds_emu"][key]
            for key in reconnect_disconnect_keys:
                if key in baseline.get("disconnect", {}):
                    target.setdefault("disconnect", {})[key] = baseline["disconnect"][key]

        elif scope == "config_2":
            for key in auto_feature_threshold_keys:
                if key in baseline.get("thresholds_emu", {}):
                    target.setdefault("thresholds_emu", {})[key] = baseline["thresholds_emu"][key]
            for key in auto_feature_disconnect_keys:
                if key in baseline.get("disconnect", {}):
                    target.setdefault("disconnect", {})[key] = baseline["disconnect"][key]
            target["device_auto_features"] = deepcopy(baseline.get("device_auto_features", {}))
            target["device_feature_profiles"] = deepcopy(baseline.get("device_feature_profiles", {}))

        self.current_config = deepcopy(target)
        self._apply_config_to_widgets(target)
        self.update_device_energy_settings()
        self.update_device_auto_feature_settings()
        if hasattr(self, "update_device_feature_profile_settings"):
            self.update_device_feature_profile_settings()
        self.update_current_config_display()
        self.config_dirty = (self.current_config != baseline)
        self.save_btn.setEnabled(self.config_dirty)
        self.reset_btn.setEnabled(self.config_dirty)
        if hasattr(self, "launch_save_btn"):
            self.launch_save_btn.setEnabled(self.config_dirty)
        if hasattr(self, "launch_reset_btn"):
            self.launch_reset_btn.setEnabled(self.config_dirty)
        self._update_auto_battle_tab_enabled()
        self._update_reconnect_tab_enabled()
        self._update_auto_features_tab_enabled()
        self._update_run_action_guard()
        self.append_log("[CONFIG] " + t("btn_reset_changes", "已重置變更"))

    def _apply_config_to_widgets(self, config_obj):
        """將指定設定物件套用到 UI 控件。"""
        emu_paths = config_obj.get("emulator_paths", {})
        for key, path_input in self.emulator_path_inputs.items():
            path_input.setText(str(emu_paths.get(key, "")))

        wait_cfg = config_obj.get("wait_times", {})
        for key, spinner in self.wait_spinners.items():
            spinner.setValue(wait_cfg.get(key, spinner.value()))

        threshold_cfg = config_obj.get("thresholds_emu", {})
        for key, spinner in self.threshold_spinners.items():
            spinner.setValue(threshold_cfg.get(key, spinner.value()))
        for key, spinner in self.disconnect_threshold_spinners.items():
            spinner.setValue(threshold_cfg.get(key, spinner.value()))

        self.energy_check.setChecked(config_obj.get("energy_strategy", self.energy_check.isChecked()))
        self.auto_battle_enable_check.setChecked(config_obj.get("auto_battle_enabled", self.auto_battle_enable_check.isChecked()))

        disconnect_cfg = config_obj.get("disconnect", {})
        self.disconnect_enable_check.setChecked(disconnect_cfg.get("enabled", self.disconnect_enable_check.isChecked()))
        self.same_screen_timeout_spin.setValue(disconnect_cfg.get("same_screen_timeout", self.same_screen_timeout_spin.value()))
        self.pc_launch_wait_timeout_spin.setValue(disconnect_cfg.get("pc_launch_wait_timeout", self.pc_launch_wait_timeout_spin.value()))

        attempts = int(disconnect_cfg.get("max_reconnect_attempts", 5))
        self.max_reconnect_unlimited_check.setChecked(attempts == 0)
        self.max_reconnect_attempts_spin.setValue(max(1, attempts) if attempts != 0 else 5)

        self.restart_game_enable_check.setChecked(disconnect_cfg.get("restart_game_enabled", self.restart_game_enable_check.isChecked()))
        self.login_game_enable_check.setChecked(disconnect_cfg.get("login_game_enabled", self.login_game_enable_check.isChecked()))
        self.auto_enable_features_check.setChecked(disconnect_cfg.get("auto_enable_features_enabled", self.auto_enable_features_check.isChecked()))
        self.auto_enable_wander_check.setChecked(disconnect_cfg.get("auto_enable_wander", self.auto_enable_wander_check.isChecked()))
        self.auto_enable_ai_check.setChecked(disconnect_cfg.get("auto_enable_ai", self.auto_enable_ai_check.isChecked()))
        self.emu_package_input.setText(disconnect_cfg.get("emu_package_name", self.emu_package_input.text()))
        self.screen_hash_diff_threshold_spin.setValue(disconnect_cfg.get("screen_hash_diff_threshold", self.screen_hash_diff_threshold_spin.value()))
        self.screen_hash_interval_spin.setValue(disconnect_cfg.get("screen_hash_interval", self.screen_hash_interval_spin.value()))
        self.action_cooldown_spin.setValue(disconnect_cfg.get("action_cooldown", self.action_cooldown_spin.value()))
        self.auto_feature_action_cooldown_spin.setValue(disconnect_cfg.get("auto_feature_action_cooldown", self.auto_feature_action_cooldown_spin.value()))
        self.auto_feature_scan_interval_spin.setValue(disconnect_cfg.get("auto_feature_scan_interval", self.auto_feature_scan_interval_spin.value()))
        self.check_game_open_interval_spin.setValue(int(disconnect_cfg.get("check_game_open_interval_emu", self.check_game_open_interval_spin.value())))
        self.login_timeout_spin.setValue(disconnect_cfg.get("login_timeout", self.login_timeout_spin.value()))
        self.post_login_timeout_spin.setValue(disconnect_cfg.get("post_login_timeout", self.post_login_timeout_spin.value()))
        self.in_game_confirm_timeout_spin.setValue(disconnect_cfg.get("in_game_confirm_timeout", self.in_game_confirm_timeout_spin.value()))

        self.current_config["device_strategies"] = deepcopy(config_obj.get("device_strategies", {}))
        self.current_config["device_auto_features"] = deepcopy(config_obj.get("device_auto_features", {}))
        self.current_config["device_feature_profiles"] = deepcopy(config_obj.get("device_feature_profiles", {}))
        if hasattr(self, "scheduled_restart_hours_spin"):
            self.scheduled_restart_hours_spin.setValue(int(disconnect_cfg.get("scheduled_restart_hours", 0)))
        if hasattr(self, "scheduled_restart_minutes_spin"):
            self.scheduled_restart_minutes_spin.setValue(int(disconnect_cfg.get("scheduled_restart_minutes", 0)))
        if hasattr(self, "scheduled_restart_global_enable_check"):
            self.scheduled_restart_global_enable_check.setChecked(bool(disconnect_cfg.get("scheduled_restart_enabled", False)))

    def restore_defaults(self):
        """恢復預設：僅套用目前選中分頁的預設值。"""
        defaults = deepcopy(self.default_config or {})
        target = deepcopy(self.current_config)

        scope = self._get_active_scope()

        auto_battle_wait_keys = {
            "scan_interval", "after_click", "pop_window", "battle_unlock", "join_confirm", "wait_battle_check"
        }
        auto_battle_threshold_keys = {
            "battle_title", "btn_add", "btn_confirm", "btn_join", "in_battle", "energy_low", "energy_9"
        }
        auto_feature_threshold_keys = set(getattr(self, "auto_feature_threshold_keys", []))
        reconnect_threshold_keys = {
            "disconnect_hint", "btn_reconnect", "btn_back_to_login", "login_from_other_place",
            "multi_login", "custom_login", "btn_login_account", "select_server", "select_character",
            "login_game_button", "start_game_announcement", "announcement", "update_resource",
            "pop_gift_box", "dont_ask_today", "btn_cross", "btn_power_saving",
        }

        reconnect_disconnect_keys = {
            "enabled", "same_screen_timeout", "max_reconnect_attempts", "pc_launch_wait_timeout",
            "restart_game_enabled", "login_game_enabled", "emu_package_name", "screen_hash_diff_threshold",
            "screen_hash_interval", "action_cooldown", "check_game_open_interval_emu", "login_timeout", "post_login_timeout",
        }
        auto_feature_disconnect_keys = {
            "auto_enable_features_enabled", "auto_enable_wander", "auto_enable_ai",
            "auto_feature_action_cooldown", "auto_feature_scan_interval", "in_game_confirm_timeout",
        }

        default_wait_times = defaults.get("wait_times", {})
        for key in target.get("wait_times", {}):
            if key in default_wait_times and (scope == "config_0" and key in auto_battle_wait_keys):
                target["wait_times"][key] = default_wait_times[key]

        default_thresholds = defaults.get("thresholds_emu", {})
        if not default_thresholds:
            default_thresholds = defaults.get("thresholds", {}).get("EMU", {})
        for key in target.get("thresholds_emu", {}):
            if key not in default_thresholds:
                continue
            if scope == "config_0" and key in auto_battle_threshold_keys:
                target["thresholds_emu"][key] = default_thresholds[key]
            elif scope == "config_1" and key in reconnect_threshold_keys:
                target["thresholds_emu"][key] = default_thresholds[key]
            elif scope == "config_2" and key in auto_feature_threshold_keys:
                target["thresholds_emu"][key] = default_thresholds[key]

        if scope == "config_0":
            for key in ["energy_strategy", "auto_battle_enabled"]:
                if key in defaults:
                    target[key] = defaults[key]

        disconnect_defaults = defaults.get("disconnect", {})
        if scope == "launch":
            target.setdefault("disconnect", {})["emu_package_name"] = disconnect_defaults.get("emu_package_name", "")
            target["emulator_paths"] = deepcopy(defaults.get("emulator_paths", {}))
        for key in list(target.get("disconnect", {}).keys()):
            if key not in disconnect_defaults:
                continue
            if scope == "config_1" and key in reconnect_disconnect_keys:
                target["disconnect"][key] = disconnect_defaults[key]
            elif scope == "config_2" and key in auto_feature_disconnect_keys:
                target["disconnect"][key] = disconnect_defaults[key]

        if scope == "config_0":
            energy_default = bool(defaults.get("energy_strategy", False))
            target.setdefault("device_strategies", {})
            strategy_serials = set(target["device_strategies"].keys()) | set(self.selected_devices)
            for serial in strategy_serials:
                target["device_strategies"][serial] = energy_default

        if scope == "config_2":
            auto_defaults = {
                "wander": bool(disconnect_defaults.get("auto_enable_wander", True)),
                "ai": bool(disconnect_defaults.get("auto_enable_ai", True)),
            }
            target.setdefault("device_auto_features", {})
            auto_serials = set(target["device_auto_features"].keys()) | set(self.selected_devices)
            for serial in auto_serials:
                target["device_auto_features"][serial] = dict(auto_defaults)
            profile_default = self._default_device_feature_profile()
            target.setdefault("device_feature_profiles", {})
            profile_serials = set(target["device_feature_profiles"].keys()) | set(self.selected_devices)
            for serial in profile_serials:
                target["device_feature_profiles"][serial] = dict(profile_default)

        self.current_config = deepcopy(target)
        self._apply_config_to_widgets(target)
        self.update_device_energy_settings()
        self.update_device_auto_feature_settings()
        if hasattr(self, "update_device_feature_profile_settings"):
            self.update_device_feature_profile_settings()
        self.update_current_config_display()
        self._update_auto_battle_tab_enabled()
        self._update_reconnect_tab_enabled()
        self._update_auto_features_tab_enabled()
        self.config_dirty = (self.current_config != self._original_config)
        self.save_btn.setEnabled(self.config_dirty)
        self.reset_btn.setEnabled(self.config_dirty)
        if hasattr(self, "launch_save_btn"):
            self.launch_save_btn.setEnabled(self.config_dirty)
        if hasattr(self, "launch_reset_btn"):
            self.launch_reset_btn.setEnabled(self.config_dirty)
        self._update_run_action_guard()
        self.append_log("[CONFIG] " + t("btn_restore_defaults", "已恢復預設"))

    def update_device_energy_settings(self):
        """更新每台設備的活力策略設定"""
        for i in reversed(range(self.device_energy_container_layout.count())):
            w = self.device_energy_container_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        self.device_energy_checks.clear()

        if not self.selected_devices:
            from PyQt5.QtWidgets import QLabel
            empty_label = QLabel(t("device_strategy_empty", "尚未選擇任何設備。請先在「啟動」頁選擇設備。"))
            self.device_energy_container_layout.addWidget(empty_label)
            return

        from PyQt5.QtWidgets import QCheckBox
        for device_serial in self.selected_devices:
            device_name = self.device_map.get(device_serial, {}).get('name', device_serial)
            check = QCheckBox(device_name)
            saved = self.current_config.get("device_configs", {}).get(device_serial, self.energy_check.isChecked())
            check.setChecked(saved)
            check.stateChanged.connect(self.on_config_changed)
            self.device_energy_checks[device_serial] = check
            self.device_energy_container_layout.addWidget(check)

    def update_device_auto_feature_settings(self):
        """更新每台設備的自動開啟功能設定"""
        for i in reversed(range(self.device_auto_feature_container_layout.count())):
            w = self.device_auto_feature_container_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        self.device_auto_feature_checks.clear()

        if not self.selected_devices:
            from PyQt5.QtWidgets import QLabel
            empty_label = QLabel(t("device_auto_feature_empty", "尚未選擇任何設備。請先在「啟動」頁選擇設備。"))
            self.device_auto_feature_container_layout.addWidget(empty_label)
            return

        default_wander = self.auto_enable_wander_check.isChecked()
        default_ai = self.auto_enable_ai_check.isChecked()

        from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QCheckBox
        for device_serial in self.selected_devices:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            device_name = self.device_map.get(device_serial, {}).get('name', device_serial)
            name_label = QLabel(device_name)
            name_label.setMinimumWidth(240)
            row_layout.addWidget(name_label)

            wander_check = QCheckBox(t("reconnect_auto_wander_short", "徘徊"))
            ai_check = QCheckBox(t("reconnect_auto_ai_short", "AI"))

            saved = self.current_config.get("device_auto_features", {}).get(device_serial, {})
            wander_check.setChecked(saved.get("wander", default_wander))
            ai_check.setChecked(saved.get("ai", default_ai))

            wander_check.stateChanged.connect(self.on_config_changed)
            ai_check.stateChanged.connect(self.on_config_changed)

            self.device_auto_feature_checks[device_serial] = {
                "wander": wander_check,
                "ai": ai_check,
            }

            enabled = self.auto_enable_features_check.isChecked()
            wander_check.setEnabled(enabled)
            ai_check.setEnabled(enabled)

            row_layout.addWidget(wander_check)
            row_layout.addWidget(ai_check)
            row_layout.addStretch()
            self.device_auto_feature_container_layout.addWidget(row)

    def _default_device_feature_profile(self):
        """回傳新設備功能開關預設值。"""
        return {
            "auto_battle_enabled": bool(self.auto_battle_enable_check.isChecked()),
            "stop_on_low_energy": bool(self.energy_check.isChecked()),
            "disconnect_enabled": bool(self.disconnect_enable_check.isChecked()),
            "auto_enable_features_enabled": bool(self.auto_enable_features_check.isChecked()),
            "scheduled_restart_enabled": bool(
                getattr(self, "scheduled_restart_global_enable_check", self.disconnect_enable_check).isChecked()
                if hasattr(self, "scheduled_restart_global_enable_check")
                else False
            ),
        }

    def update_device_feature_profile_settings(self):
        """更新每設備功能配置（共用於 PC/EMU）。"""
        if not hasattr(self, "device_feature_profile_container_layout"):
            return
        clear_layout_widgets(self.device_feature_profile_container_layout)
        self.device_feature_profile_checks = {}

        selected = list(getattr(self, "selected_devices", []) or [])
        if not selected:
            from PyQt5.QtWidgets import QLabel
            empty_label = QLabel(t("device_feature_empty", "尚未選擇任何設備。請先在「啟動」頁選擇設備。"))
            self.device_feature_profile_container_layout.addWidget(empty_label)
            return

        defaults = self._default_device_feature_profile()
        profile_map = self.current_config.setdefault("device_feature_profiles", {})
        for serial in selected:
            device_name = self.device_map.get(serial, {}).get("name", serial)
            profile = dict(defaults)
            profile.update(profile_map.get(serial, {}))
            row, widgets = build_device_feature_row(device_name, profile, self.on_config_changed, t)
            self.device_feature_profile_container_layout.addWidget(row)
            self.device_feature_profile_checks[serial] = widgets

    def apply_batch_device_feature_profile(self):
        """將批次開關套用到目前選擇的設備。"""
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
