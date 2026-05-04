"""
配置載入 / 儲存 / 預設值管理

支援 PC 與 EMU 分開的配置檔:
  bot_config_pc.json   - PC 模式專用
  bot_config_emu.json  - EMU 模式專用
"""
import os
import json
from copy import deepcopy

from .constants import resource_path, CONFIG_FILE_PC, CONFIG_FILE_EMU
from .logger import bot_log

# ---- 全域配置 ----
DEFAULT_CONFIG = None
RUNNING_CONFIG = None


def _hardcoded_defaults():
    """當所有 JSON 檔都載入失敗時的最終後備值"""
    return {
        "wait_times": {
            "scan_interval": 1.0,
            "after_click": 0.1,
            "pop_window": 0.1,
            "battle_unlock": 1.0,
            "join_confirm": 0.1,
            "wait_battle_check": 30.0,
        },
        "energy_strategy": False,
        "auto_battle_enabled": True,
        "thresholds": {
            "PC": {
                "battle_title": 0.80, "btn_add": 0.80, "btn_confirm": 0.80,
                "btn_join": 0.80, "in_battle": 0.80, "energy_low": 0.9, "energy_9": 0.92,
                "disconnect_hint": 0.70, "btn_reconnect": 0.80, "btn_back_to_login": 0.80,
                "multi_login": 0.80, "custom_login": 0.80,
                "btn_login_account": 0.80, "select_server": 0.80, "select_character": 0.80,
                "login_game_button": 0.80, "pop_gift_box": 0.80, "start_game_announcement": 0.80,
                "announcement": 0.80, "dont_ask_today": 0.80,
                "btn_cross": 0.80, "btn_power_saving": 0.80,
                "btn_wander_on": 0.85, "btn_wander_off": 0.91,
                "btn_ai": 0.90, "btn_ai_off_in_battle": 0.80,
                            "update_resource": 0.80,
            },
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
                            "update_resource": 0.70,
            },
        },
        "device_configs": {},
        "device_feature_profiles": {},
        "disconnect": {
            "enabled": True,
            "same_screen_timeout": 45.0,
            "screen_hash_interval": 1.0,
            "screen_hash_diff_threshold": 5.0,
            "max_reconnect_attempts": 5,
            "action_cooldown": 1.0,
            "auto_feature_scan_interval": 0.6,
            "login_timeout": 120.0,
            "post_login_timeout": 45.0,
            "in_game_confirm_timeout": 25.0,
            "pc_launch_wait_timeout": 25.0,
            "restart_game_enabled": True,
            "login_game_enabled": True,
            "auto_enable_features_enabled": True,
            "auto_enable_wander": True,
            "auto_enable_ai": True,
            "scheduled_restart_enabled": False,
            "scheduled_restart_hours": 0,
            "scheduled_restart_minutes": 0,
            "pc_exe_path": "",
            "emu_package_name": "",
            "check_game_open_interval_pc": 60.0,
            "check_game_open_interval_emu": 60.0,
        },
    }


def load_default_config(platform=None):
    """
    從 default_config*.json 載入預設配置。
    platform: "PC" / "EMU" / None(載入通用)
    """
    global DEFAULT_CONFIG

    # 優先嘗試平台專用預設檔
    if platform == "PC":
        try:
            with open(resource_path("default_config_pc.json"), "r", encoding="utf-8") as f:
                DEFAULT_CONFIG = json.load(f)
                return DEFAULT_CONFIG
        except Exception:
            pass
    elif platform == "EMU":
        try:
            with open(resource_path("default_config_emu.json"), "r", encoding="utf-8") as f:
                DEFAULT_CONFIG = json.load(f)
                return DEFAULT_CONFIG
        except Exception:
            pass

    # 通用預設檔
    try:
        with open(resource_path("default_config.json"), "r", encoding="utf-8") as f:
            DEFAULT_CONFIG = json.load(f)
            return DEFAULT_CONFIG
    except Exception as e:
        print(f"Failed to load default_config.json: {e}")
        DEFAULT_CONFIG = _hardcoded_defaults()
        return DEFAULT_CONFIG


def get_config_file(mode):
    """根據模式取得對應的配置檔名"""
    return CONFIG_FILE_PC if mode == "1" else CONFIG_FILE_EMU


def deep_update(d, u):
    """遞歸更新字典"""
    for k, v in u.items():
        if isinstance(v, dict):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d


def _print_saved_config_summary(saved_config, default_config, platform):
    """列印上次配置摘要，方便 CLI 快速確認是否沿用。"""
    print("等待時間設定：")
    for key, val in saved_config.get("wait_times", {}).items():
        default_val = default_config.get("wait_times", {}).get(key, val)
        print(f"  {key:20} = {val:6.1f} (預設 {default_val:6.1f})")

    print("\n活力策略設定：")
    strategy_str = "停止等待" if saved_config.get("energy_strategy", False) else "自動回復"
    default_str = "停止等待" if default_config.get("energy_strategy", False) else "自動回復"
    print(f"  低活力時         = {strategy_str:8} (預設 {default_str})")
    auto_battle_str = "啟用" if saved_config.get("auto_battle_enabled", True) else "停用"
    auto_battle_default = "啟用" if default_config.get("auto_battle_enabled", True) else "停用"
    print(f"  自動戰鬥功能     = {auto_battle_str:8} (預設 {auto_battle_default})")

    print("\n斷線重連設定：")
    saved_disconnect = saved_config.get("disconnect", {})
    default_disconnect = default_config.get("disconnect", {})
    disconnect_fields = [
        ("enabled", "啟用斷線重連"),
        ("same_screen_timeout", "同畫面逾時"),
        ("max_reconnect_attempts", "最大重連次數"),
        ("screen_hash_interval", "辨識畫面間隔"),
        ("screen_hash_diff_threshold", "同畫面差異閾值"),
        ("action_cooldown", "點擊等待(s)"),
        ("auto_feature_scan_interval", "辨識畫面間隔"),
        ("login_timeout", "登入逾時(s)"),
        ("post_login_timeout", "登入後逾時(s)"),
        ("in_game_confirm_timeout", "遊戲內確認逾時(s)"),
        ("pc_launch_wait_timeout", "重啟等待時間"),
        ("restart_game_enabled", "流程A 重開遊戲"),
        ("login_game_enabled", "流程B 登入遊戲"),
        ("auto_enable_features_enabled", "流程C 自動開啟功能"),
        ("auto_enable_wander", "自動開啟徘徊"),
        ("auto_enable_ai", "自動開啟 AI"),
        ("scheduled_restart_enabled", "定時重開啟用"),
        ("scheduled_restart_hours", "定時重開時數"),
        ("scheduled_restart_minutes", "定時重開分鐘"),
    ]
    if platform == "PC":
        disconnect_fields.extend([
            ("check_game_open_interval_pc", "遊戲開啟檢查間隔(分)"),
            ("pc_exe_path", "PC 遊戲 EXE 路徑"),
        ])
    else:
        disconnect_fields.extend([
            ("check_game_open_interval_emu", "遊戲開啟檢查間隔(分)"),
            ("emu_package_name", "EMU 套件名稱"),
        ])

    for key, label in disconnect_fields:
        if key not in saved_disconnect and key not in default_disconnect:
            continue
        val = saved_disconnect.get(key, default_disconnect.get(key))
        default_val = default_disconnect.get(key, val)
        print(f"  {label:22} = {val} (預設 {default_val})")

    print(f"\n{platform} 主要閾值：")
    saved_thresholds = saved_config.get("thresholds", {}).get(platform, {})
    default_thresholds = default_config.get("thresholds", {}).get(platform, {})
    threshold_keys = [
        "battle_title",
        "btn_join",
        "disconnect_hint",
        "btn_reconnect",
        "select_server",
        "login_game_button",
        "pop_gift_box",
        "announcement",
        "update_resource",
        "btn_power_saving",
        "btn_wander_on",
        "btn_ai",
    ]
    for key in threshold_keys:
        val = saved_thresholds.get(key)
        default_val = default_thresholds.get(key, val)
        if val is None:
            continue
        print(f"  {key:22} = {val:.2f} (預設 {default_val:.2f})")
    print(f"  {'threshold_count':22} = {len(saved_thresholds)}")


# ---- CLI 互動式配置載入 ----

def load_config(mode="2"):
    """
    統一的配置加載系統（CLI 模式）
    mode: "1"=PC, "2"=EMU
    """
    global RUNNING_CONFIG, DEFAULT_CONFIG

    platform = "PC" if mode == "1" else "EMU"
    DEFAULT_CONFIG = load_default_config(platform)
    RUNNING_CONFIG = deepcopy(DEFAULT_CONFIG)

    config_file = get_config_file(mode)

    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                saved_config = json.load(f)

            print(f"\n【已偵測到上次的配置】({config_file})")
            print("─" * 50)
            _print_saved_config_summary(saved_config, DEFAULT_CONFIG, platform)
            print("─" * 50)

            ans = input("\n是否套用上次的配置？(Y/n): ").strip().lower()
            if ans != "n":
                RUNNING_CONFIG = deepcopy(DEFAULT_CONFIG)
                deep_update(RUNNING_CONFIG, saved_config)
                print("[OK] 已套用上次的配置！")
                return True
        except Exception as e:
            print(f"[WARN] 讀取配置異常: {e}")

    print("\n【開始設定配置】")
    print("=" * 50)

    print("\n1. 等待時間設定")
    print("   (掃描間隔、點擊後等待、彈窗等待、戰鬥解鎖、確認等待、等待戰鬥檢查)")
    ans = input("   是否自訂？(Y/n): ").strip().lower()
    if ans != "n":
        print("\n【等待時間設定】")
        for key in RUNNING_CONFIG["wait_times"].keys():
            default_val = DEFAULT_CONFIG["wait_times"][key]
            new_val = input(f"  {key:20} (預設 {default_val}): ").strip()
            if new_val:
                try:
                    RUNNING_CONFIG["wait_times"][key] = float(new_val)
                except Exception:
                    RUNNING_CONFIG["wait_times"][key] = default_val

    print("\n2. 分數門檻設定")
    print(f"   ({platform} 版本)")
    ans = input("   是否自訂？(y/N): ").strip().lower()
    if ans == "y":
        print(f"\n【{platform} 版本】")
        thresholds = DEFAULT_CONFIG.get("thresholds", {}).get(platform, {})
        if platform not in RUNNING_CONFIG.get("thresholds", {}):
            RUNNING_CONFIG.setdefault("thresholds", {})[platform] = {}
        for key, default_val in thresholds.items():
            new_val = input(f"  {key:15} (預設 {default_val:.2f}): ").strip()
            if new_val:
                try:
                    RUNNING_CONFIG["thresholds"][platform][key] = float(new_val)
                except Exception:
                    RUNNING_CONFIG["thresholds"][platform][key] = default_val

    print("\n3. 活力策略設定")
    print("   低活力時的行動方式")
    ans = input("   是否自訂？(y/N): ").strip().lower()
    if ans == "y":
        print("\n   False (f) - 自動回復到滿 (預設)")
        print("   True  (t) - 停止流程，等待活力恢復")
        val = input("   請選擇 (f/t): ").strip().lower()
        if val in ["t", "true"]:
            RUNNING_CONFIG["energy_strategy"] = True
        else:
            RUNNING_CONFIG["energy_strategy"] = False

    print("\n3.5 自動戰鬥功能")
    print("   是否啟用自動搜尋對手與自動點擊流程")
    ans = input("   是否啟用？(Y/n): ").strip().lower()
    RUNNING_CONFIG["auto_battle_enabled"] = (ans != "n")

    print("\n4. 斷線重連設定")
    print("   (同畫面卡住偵測、重連次數、登入流程參數)")
    ans = input("   是否自訂？(y/N): ").strip().lower()
    if ans == "y":
        disconnect_cfg = RUNNING_CONFIG.setdefault("disconnect", {})
        default_disconnect = DEFAULT_CONFIG.get("disconnect", {})

        enabled_default = disconnect_cfg.get("enabled", default_disconnect.get("enabled", True))
        enabled_ans = input(
            f"   啟用斷線重連 (y/n，預設 {'y' if enabled_default else 'n'}): "
        ).strip().lower()
        if enabled_ans in {"y", "n"}:
            disconnect_cfg["enabled"] = (enabled_ans == "y")
        else:
            disconnect_cfg["enabled"] = bool(enabled_default)

        same_screen_default = disconnect_cfg.get(
            "same_screen_timeout", default_disconnect.get("same_screen_timeout", 45.0)
        )
        same_screen_val = input(
            f"   同畫面卡住秒數 (預設 {same_screen_default}): "
        ).strip()
        if same_screen_val:
            try:
                disconnect_cfg["same_screen_timeout"] = float(same_screen_val)
            except Exception:
                disconnect_cfg["same_screen_timeout"] = same_screen_default

        reconnect_default = disconnect_cfg.get(
            "max_reconnect_attempts", default_disconnect.get("max_reconnect_attempts", 5)
        )
        reconnect_val = input(
            f"   最大重連次數 (預設 {reconnect_default}): "
        ).strip()
        if reconnect_val:
            try:
                disconnect_cfg["max_reconnect_attempts"] = int(reconnect_val)
            except Exception:
                disconnect_cfg["max_reconnect_attempts"] = reconnect_default

        login_timeout_default = disconnect_cfg.get(
            "login_timeout", default_disconnect.get("login_timeout", 120.0)
        )
        login_timeout_val = input(
            f"   登入流程逾時秒數 (預設 {login_timeout_default}): "
        ).strip()
        if login_timeout_val:
            try:
                disconnect_cfg["login_timeout"] = float(login_timeout_val)
            except Exception:
                disconnect_cfg["login_timeout"] = login_timeout_default

        if platform == "PC":
            pc_exe_default = disconnect_cfg.get("pc_exe_path", default_disconnect.get("pc_exe_path", ""))
            pc_exe_val = input(
                f"   PC 遊戲 EXE 路徑 (留空維持，目前: {pc_exe_default or '未設定'}): "
            ).strip()
            if pc_exe_val:
                disconnect_cfg["pc_exe_path"] = pc_exe_val
        else:
            emu_pkg_default = disconnect_cfg.get(
                "emu_package_name", default_disconnect.get("emu_package_name", "")
            )
            emu_pkg_val = input(
                f"   EMU 遊戲套件名 (留空維持，目前: {emu_pkg_default or '未設定'}): "
            ).strip()
            if emu_pkg_val:
                disconnect_cfg["emu_package_name"] = emu_pkg_val

    print("\n[OK] 配置設定完成")
    print("=" * 50)

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(RUNNING_CONFIG, f, indent=4, ensure_ascii=False)
    print(f"[SAVE] 配置已儲存到 {config_file}")

    return False


def setup_device_configs(target_devices):
    """設定設備特定的活力策略配置"""
    if "device_configs" not in RUNNING_CONFIG:
        RUNNING_CONFIG["device_configs"] = {}

    if len(target_devices) <= 1:
        for device_id in target_devices:
            RUNNING_CONFIG["device_configs"][device_id] = RUNNING_CONFIG["energy_strategy"]
        return

    ans = input(
        f"\n多設備偵測 ({len(target_devices)} 台)，是否為每台設備分別配置活力策略？(y/N): "
    ).strip().lower()
    if ans == "y":
        print("\n【設備活力策略配置】")
        for device_id in target_devices:
            print(f"\n[DEVICE] {device_id}")
            print(f"   (預設: {RUNNING_CONFIG['energy_strategy']})")
            val = input("   低活力時是否停止？(y/N): ").strip().lower()
            RUNNING_CONFIG["device_configs"][device_id] = (val == "y")
    else:
        for device_id in target_devices:
            RUNNING_CONFIG["device_configs"][device_id] = RUNNING_CONFIG["energy_strategy"]


def log_device_configs(device_ids):
    """GUI 模式下將每台設備的活力策略顯示到 UI 日誌"""
    for device_id in device_ids:
        strategy = RUNNING_CONFIG["device_configs"].get(
            device_id, RUNNING_CONFIG["energy_strategy"]
        )
        strategy_text = "停止等待" if strategy else "自動回復"
        bot_log("CONFIG", f"{device_id} 活力策略: {strategy_text}")


# ---- 模組初始化：載入通用預設配置 ----
DEFAULT_CONFIG = load_default_config()
RUNNING_CONFIG = deepcopy(DEFAULT_CONFIG)
