"""
gui/pc_display.py
PCDisplayMixin - PC 模式欄位變更高亮與設定顯示 mixin
"""

import re

from PyQt5.QtWidgets import QCheckBox

from i18n import t


class PCDisplayMixin:
    """PC 模式設定顯示 mixin：變更高亮、原值標注"""

    def _ensure_display_state(self):
        if not hasattr(self, "_label_base_texts"):
            self._label_base_texts = {}
        if not hasattr(self, "_checkbox_base_texts"):
            self._checkbox_base_texts = {}
        if not hasattr(self, "_widget_base_styles"):
            self._widget_base_styles = {}

    def _save_widget_base_style(self, widget):
        self._ensure_display_state()
        if widget not in self._widget_base_styles:
            self._widget_base_styles[widget] = widget.styleSheet()

    def _set_widget_changed_style(self, widget, changed):
        self._save_widget_base_style(widget)
        base = self._widget_base_styles.get(widget, "")
        if not changed:
            widget.setStyleSheet(base)
            return

        if isinstance(widget, QCheckBox):
            extra = "color: #c62828;"
        else:
            extra = "border: 1px solid #c62828; background-color: #fff5f5;"
        widget.setStyleSheet((base + " " + extra).strip())

    def _clean_changed_suffix(self, text):
        if not isinstance(text, str):
            return ""
        original_label = t("original_value_label", "原")
        return re.sub(rf"\s*\({original_label}:\s*.*\)\s*:?\s*$", "", text).strip()

    def _set_label_changed_text(self, label, changed, original_text):
        self._ensure_display_state()
        if label not in self._label_base_texts:
            self._label_base_texts[label] = self._clean_changed_suffix(label.text())
        base = self._clean_changed_suffix(self._label_base_texts.get(label, label.text()))
        base_with_colon = base if base.endswith(":") else f"{base}:"
        self._label_base_texts[label] = base_with_colon
        if changed:
            base_no_colon = base_with_colon[:-1]
            original_label = t("original_value_label", "原")
            label.setText(f"{base_no_colon} ({original_label}: {original_text}):")
            label.setStyleSheet("color: #c62828; font-weight: 600;")
        else:
            label.setText(base_with_colon)
            label.setStyleSheet("")

    def _set_checkbox_changed_text(self, checkbox, changed, original_text):
        self._ensure_display_state()
        if checkbox not in self._checkbox_base_texts:
            self._checkbox_base_texts[checkbox] = self._clean_changed_suffix(checkbox.text())
        base = self._clean_changed_suffix(self._checkbox_base_texts.get(checkbox, checkbox.text()))
        self._checkbox_base_texts[checkbox] = base
        if changed:
            original_label = t("original_value_label", "原")
            checkbox.setText(f"{base} ({original_label}: {original_text})")
        else:
            checkbox.setText(base)
        self._set_widget_changed_style(checkbox, changed)

    def _fmt_original_bool(self, value):
        return t("status_enabled", "啟用") if bool(value) else t("status_disabled", "停用")

    def _fmt_original_number(self, value, decimals=1):
        return f"{float(value):.{int(decimals)}f}"

    def update_current_config_display(self):
        """以紅字標示與原始設定不同的欄位，並註記原值。"""
        self._ensure_display_state()
        original = getattr(self, "_original_config", {}) or {}
        original_disconnect = original.get("disconnect", {})

        # 自動玩家對戰分頁
        for key, spinner in self.wait_spinners.items():
            orig_val = float(original.get("wait_times", {}).get(key, spinner.value()))
            changed = abs(spinner.value() - orig_val) > 1e-9
            self._set_widget_changed_style(spinner, changed)
            label = self.wait_labels.get(key)
            if label:
                self._set_label_changed_text(label, changed, self._fmt_original_number(orig_val, 1))

        for key, spinner in self.threshold_spinners.items():
            orig_val = float(original.get("thresholds_pc", {}).get(key, spinner.value()))
            changed = abs(spinner.value() - orig_val) > 1e-9
            self._set_widget_changed_style(spinner, changed)
            label = self.threshold_labels.get(key)
            if label:
                self._set_label_changed_text(label, changed, self._fmt_original_number(orig_val, 2))

        self._set_checkbox_changed_text(
            self.auto_battle_enable_check,
            self.auto_battle_enable_check.isChecked() != bool(original.get("auto_battle_enabled", self.auto_battle_enable_check.isChecked())),
            self._fmt_original_bool(original.get("auto_battle_enabled", self.auto_battle_enable_check.isChecked())),
        )
        self._set_checkbox_changed_text(
            self.energy_check,
            self.energy_check.isChecked() != bool(original.get("energy_strategy", self.energy_check.isChecked())),
            self._fmt_original_bool(original.get("energy_strategy", self.energy_check.isChecked())),
        )

        # 斷線重連分頁
        self._set_checkbox_changed_text(
            self.disconnect_enable_check,
            self.disconnect_enable_check.isChecked() != bool(original_disconnect.get("enabled", self.disconnect_enable_check.isChecked())),
            self._fmt_original_bool(original_disconnect.get("enabled", self.disconnect_enable_check.isChecked())),
        )

        reconnect_fields = [
            (self.reconnect_wait_left_form, self.same_screen_timeout_spin, float(original_disconnect.get("same_screen_timeout", self.same_screen_timeout_spin.value())), 1),
            (self.reconnect_wait_left_form, self.action_cooldown_spin, float(original_disconnect.get("action_cooldown", self.action_cooldown_spin.value())), 1),
            (self.reconnect_wait_right_form, self.pc_launch_wait_timeout_spin, float(original_disconnect.get("pc_launch_wait_timeout", self.pc_launch_wait_timeout_spin.value())), 0),
            (self.reconnect_wait_right_form, self.screen_hash_interval_spin, float(original_disconnect.get("screen_hash_interval", self.screen_hash_interval_spin.value())), 1),
            (self.reconnect_wait_right_form, self.check_game_open_interval_spin, float(original_disconnect.get("check_game_open_interval_pc", self.check_game_open_interval_spin.value())), 0),
            (self.reconnect_wait_left_form, self.login_timeout_spin, float(original_disconnect.get("login_timeout", self.login_timeout_spin.value())), 0),
            (self.reconnect_wait_left_form, self.post_login_timeout_spin, float(original_disconnect.get("post_login_timeout", self.post_login_timeout_spin.value())), 0),
        ]
        for form, field, orig_val, decimals in reconnect_fields:
            changed = abs(float(field.value()) - orig_val) > 1e-9
            self._set_widget_changed_style(field, changed)
            label = form.labelForField(field)
            if label:
                self._set_label_changed_text(label, changed, self._fmt_original_number(orig_val, decimals))

        screen_diff_changed = abs(float(self.screen_hash_diff_threshold_spin.value()) - float(original_disconnect.get("screen_hash_diff_threshold", self.screen_hash_diff_threshold_spin.value()))) > 1e-9
        self._set_widget_changed_style(self.screen_hash_diff_threshold_spin, screen_diff_changed)
        if hasattr(self, "disconnect_threshold_form"):
            label = self.disconnect_threshold_form.labelForField(self.screen_hash_diff_threshold_spin)
            if label:
                self._set_label_changed_text(
                    label,
                    screen_diff_changed,
                    self._fmt_original_number(float(original_disconnect.get("screen_hash_diff_threshold", self.screen_hash_diff_threshold_spin.value())), 1),
                )

        orig_attempts = int(original_disconnect.get("max_reconnect_attempts", 5))
        orig_unlimited = (orig_attempts == 0)
        current_unlimited = self.max_reconnect_unlimited_check.isChecked()
        current_attempts = int(self.max_reconnect_attempts_spin.value())
        orig_attempts_display = 5 if orig_unlimited else max(1, orig_attempts)
        attempts_changed = (current_unlimited != orig_unlimited) or (not current_unlimited and current_attempts != orig_attempts_display)
        label = self.disconnect_form.labelForField(self._max_attempts_layout)
        if label:
            self._set_label_changed_text(label, attempts_changed, "∞" if orig_unlimited else str(orig_attempts_display))
        self._set_checkbox_changed_text(self.max_reconnect_unlimited_check, current_unlimited != orig_unlimited, self._fmt_original_bool(orig_unlimited))
        self._set_widget_changed_style(self.max_reconnect_attempts_spin, attempts_changed and not current_unlimited)

        orig_pc_exe = str(original_disconnect.get("pc_exe_path", "") or "")
        pc_exe_changed = self.pc_exe_path_input.text().strip() != orig_pc_exe
        self._set_widget_changed_style(self.pc_exe_path_input, pc_exe_changed)
        if hasattr(self, "pc_exe_path_label"):
            self._set_label_changed_text(self.pc_exe_path_label, pc_exe_changed, orig_pc_exe or t("config_not_set", "未設定"))

        for key, spinner in self.disconnect_threshold_spinners.items():
            if key in self.auto_feature_threshold_keys:
                continue
            orig_val = float(original.get("thresholds_pc", {}).get(key, spinner.value()))
            changed = abs(spinner.value() - orig_val) > 1e-9
            self._set_widget_changed_style(spinner, changed)
            label = self.disconnect_threshold_labels.get(key)
            if label:
                self._set_label_changed_text(label, changed, self._fmt_original_number(orig_val, 2))

        # 自動開啟功能分頁
        self._set_checkbox_changed_text(
            self.auto_enable_features_check,
            self.auto_enable_features_check.isChecked() != bool(original_disconnect.get("auto_enable_features_enabled", self.auto_enable_features_check.isChecked())),
            self._fmt_original_bool(original_disconnect.get("auto_enable_features_enabled", self.auto_enable_features_check.isChecked())),
        )
        self._set_checkbox_changed_text(
            self.auto_enable_wander_check,
            self.auto_enable_wander_check.isChecked() != bool(original_disconnect.get("auto_enable_wander", self.auto_enable_wander_check.isChecked())),
            self._fmt_original_bool(original_disconnect.get("auto_enable_wander", self.auto_enable_wander_check.isChecked())),
        )
        self._set_checkbox_changed_text(
            self.auto_enable_ai_check,
            self.auto_enable_ai_check.isChecked() != bool(original_disconnect.get("auto_enable_ai", self.auto_enable_ai_check.isChecked())),
            self._fmt_original_bool(original_disconnect.get("auto_enable_ai", self.auto_enable_ai_check.isChecked())),
        )

        auto_feature_fields = [
            (getattr(self, "auto_feature_scan_interval_label", None), self.auto_feature_scan_interval_spin, float(original_disconnect.get("auto_feature_scan_interval", self.auto_feature_scan_interval_spin.value())), 1),
            (getattr(self, "auto_feature_action_cooldown_label", None), self.auto_feature_action_cooldown_spin, float(original_disconnect.get("auto_feature_action_cooldown", original_disconnect.get("action_cooldown", self.auto_feature_action_cooldown_spin.value()))), 1),
            (getattr(self, "in_game_confirm_timeout_label", None), self.in_game_confirm_timeout_spin, float(original_disconnect.get("in_game_confirm_timeout", self.in_game_confirm_timeout_spin.value())), 0),
        ]
        for label, field, orig_val, decimals in auto_feature_fields:
            changed = abs(float(field.value()) - orig_val) > 1e-9
            self._set_widget_changed_style(field, changed)
            if label:
                self._set_label_changed_text(label, changed, self._fmt_original_number(orig_val, decimals))

        for key in self.auto_feature_threshold_keys:
            if key not in self.disconnect_threshold_spinners:
                continue
            spinner = self.disconnect_threshold_spinners[key]
            orig_val = float(original.get("thresholds_pc", {}).get(key, spinner.value()))
            changed = abs(spinner.value() - orig_val) > 1e-9
            self._set_widget_changed_style(spinner, changed)
            label = self.disconnect_threshold_labels.get(key)
            if label:
                self._set_label_changed_text(label, changed, self._fmt_original_number(orig_val, 2))
