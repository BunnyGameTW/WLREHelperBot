"""
gui/device_feature_shared.py
PC / EMU 共用：每設備功能設定列與批次套用工具
"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QCheckBox


def clear_layout_widgets(layout):
    """移除 layout 下所有 widget。"""
    for i in reversed(range(layout.count())):
        item = layout.itemAt(i)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)


def build_device_feature_row(device_name, profile, on_changed, text_getter):
    """建立單一設備的功能開關列。"""
    row = QWidget()
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(8)

    name_label = QLabel(device_name)
    name_label.setMinimumWidth(240)
    row_layout.addWidget(name_label)

    auto_battle = QCheckBox(text_getter("device_feature_auto_battle_short", "對戰"))
    stop_on_low_energy = QCheckBox(text_getter("device_feature_energy_short", "停補"))
    disconnect = QCheckBox(text_getter("device_feature_disconnect_short", "重連"))
    auto_features = QCheckBox(text_getter("device_feature_auto_features_short", "自動開啟"))
    scheduled_restart = QCheckBox(text_getter("device_feature_scheduled_restart_short", "定時重開"))

    auto_battle.setChecked(bool(profile.get("auto_battle_enabled", True)))
    stop_on_low_energy.setChecked(bool(profile.get("stop_on_low_energy", False)))
    disconnect.setChecked(bool(profile.get("disconnect_enabled", True)))
    auto_features.setChecked(bool(profile.get("auto_enable_features_enabled", True)))
    scheduled_restart.setChecked(bool(profile.get("scheduled_restart_enabled", False)))

    for widget in (auto_battle, stop_on_low_energy, disconnect, auto_features, scheduled_restart):
        widget.stateChanged.connect(on_changed)
        row_layout.addWidget(widget)

    row_layout.addStretch()

    return row, {
        "auto_battle_enabled": auto_battle,
        "stop_on_low_energy": stop_on_low_energy,
        "disconnect_enabled": disconnect,
        "auto_enable_features_enabled": auto_features,
        "scheduled_restart_enabled": scheduled_restart,
    }
