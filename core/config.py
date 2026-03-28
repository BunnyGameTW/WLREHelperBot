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
        "thresholds": {
            "PC": {
                "title": 0.80, "btn_add": 0.80, "btn_confirm": 0.80,
                "btn_join": 0.80, "in_battle": 0.80, "energy_low": 0.9, "energy_9": 0.92,
            },
            "EMU": {
                "title": 0.70, "btn_add": 0.70, "btn_confirm": 0.70,
                "btn_join": 0.70, "in_battle": 0.70, "energy_low": 0.74, "energy_9": 0.88,
            },
        },
        "device_configs": {},
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
            print("等待時間設定：")
            for key, val in saved_config.get("wait_times", {}).items():
                default_val = DEFAULT_CONFIG.get("wait_times", {}).get(key, val)
                print(f"  {key:20} = {val:6.1f} (預設 {default_val:6.1f})")

            print("\n活力策略設定：")
            strategy_str = "停止等待" if saved_config.get("energy_strategy", False) else "自動回復"
            default_str = "停止等待" if DEFAULT_CONFIG.get("energy_strategy", False) else "自動回復"
            print(f"  低活力時         = {strategy_str:8} (預設 {default_str})")
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
