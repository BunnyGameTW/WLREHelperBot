"""
autoPVE - 自動對戰主入口
核心邏輯已拆分至 core/ 套件，本檔案保留 main() 與向後相容匯出。
"""
import time
import os
import sys
import ctypes
import threading
from copy import deepcopy

# ---- 從 core/ 匯入所有公開 API（向後相容） ----
from core.constants import (
    BASE_W, BASE_H, WINDOW_TITLE, THRESHOLD,
    TEMPLATES_PATHS, CONFIG_FILE_PC, CONFIG_FILE_EMU,
    resource_path,
)
from core.logger import (
    bot_log, set_log_queue, set_cmd_input_enabled,
)
from core import logger as _logger
from core.state import (
    LOCK, PC_WINDOWS,
    set_debug_mode, set_paused,
)
from core import state as _state
from core.config import (
    deep_update, get_config_file,
    load_config, setup_device_configs, log_device_configs,
    load_default_config,
)
from core import config as _config
from core.templates import load_templates, LOADED_TEMPLATES
from core.performance import PerformanceMonitor
from core.device_utils import (
    connect_adb, find_pc_game_windows, input_listener,
    get_device_display_name, get_device_custom_name, get_device_model_name,
    find_ldplayer_console_path, get_ldplayer_instances,
    get_ldplayer_custom_name_by_serial, get_ldplayer_custom_names,
    is_ldplayer_device,
)
from core.bot import DriftBot
from core.disconnect_handler import DisconnectHandler

# ---- 向後相容的屬性代理 ----
# 讓 `autoPVE.RUNNING_FROM_GUI` / `autoPVE.RUNNING_CONFIG` 等和舊版一樣能存取

def __getattr__(name):
    """模組層級 __getattr__，讓舊程式碼可以透過 autoPVE.XXX 存取全域狀態"""
    if name == "RUNNING_FROM_GUI":
        return _logger.RUNNING_FROM_GUI
    if name == "RUNNING_CONFIG":
        return _config.RUNNING_CONFIG
    if name == "DEFAULT_CONFIG":
        return _config.DEFAULT_CONFIG
    if name == "DEBUG_MODE":
        return _state.DEBUG_MODE
    if name == "PAUSED":
        return _state.PAUSED
    if name == "LOG_QUEUE":
        return _logger.LOG_QUEUE
    if name == "CMD_INPUT_ENABLED":
        return _logger.CMD_INPUT_ENABLED
    raise AttributeError(f"module 'autoPVE' has no attribute {name!r}")


# ---- DPI 感知設定 ----
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()


# --- 主流程 ---

def main(from_gui=False, log_queue=None, config_override=None, mode_override=None):
    """
    主函數
    Args:
        from_gui: 是否從 GUI 啟動
        log_queue: 可選的日誌隊列（來自 GUI）
        config_override: 可選的配置覆蓋（來自 GUI）
        mode_override: 可選的模式預設 ("1"=PC, "2"=EMU)，跳過互動選擇
    """
    _logger.RUNNING_FROM_GUI = bool(from_gui)

    if from_gui and config_override:
        platform = "PC" if config_override.get("mode") == "1" else "EMU"
        if _config.DEFAULT_CONFIG is None:
            load_default_config(platform)
        _config.RUNNING_CONFIG = deep_update(
            deepcopy(_config.DEFAULT_CONFIG), config_override
        )
    elif not from_gui:
        # 先取得模式，才能載入對應平台的配置
        if mode_override:
            load_config(mode=mode_override)
        else:
            # 預先詢問模式，再載入
            pass  # 由下方 CLI 互動決定

    if not from_gui:
        # ===== 命令行交互模式 =====
        print("=" * 50)
        print("  女王化身為無情的戰爭機器 小助手")
        from core.constants import resource_path as _rp
        try:
            with open(_rp("VERSION"), "r", encoding="utf-8") as _vf:
                _ver = _vf.read().strip()
        except Exception:
            _ver = "0.1.0"
        print(f"  v{_ver}")
        print("=" * 50)
        print("【執行模式】")
        print("1. PC 模式       (只能單開，使用 pydirectinput)")
        print("2. 模擬器模式    (支援多開，背景執行，使用 ADB)")
        print("\n【控制台快捷鍵】(執行中可使用)")
        print("Ctrl+D  - 開啟/關閉除錯模式")
        print("Ctrl+P  - 暂停/繼續偵測")
        print("Ctrl+C  - 停止腳本")
        print("=" * 50)
        if mode_override:
            mode = mode_override
            mode_name = "PC 模式" if mode == "1" else "模擬器模式"
            print(f"\n[INFO] 已預設模式: {mode_name}")
        else:
            mode = input("\n請選擇模式 (1/2): ").strip()
            # 根據選擇的模式載入對應配置
            load_config(mode=mode)
    else:
        # ===== GUI 模式：使用提供的配置 =====
        mode = _config.RUNNING_CONFIG.get("mode", "2")

    bots = []
    target_devices = []

    if mode == "2":
        # GUI 模式下，直接使用傳入的設備
        if from_gui:
            target_devices = _config.RUNNING_CONFIG.get("target_devices", [])
            if not target_devices:
                bot_log("DEVICE", "GUI模式下未選擇任何設備。")
                return bots
        else:
            devices = connect_adb()
            if not devices:
                bot_log(
                    "DEVICE",
                    "找不到任何模擬器，請確認 ADB 是否啟動或模擬器『USB偵錯』已開。",
                )
                return bots

            if len(devices) > 1:
                print("\n[DEVICE] 偵測到多台設備:")
                for i, d in enumerate(devices):
                    print(f"[{i}] {get_device_display_name(d)}")
                choice = input(
                    "\n請輸入要執行的設備編號 (用逗號分隔，例如 0,1)。\n直接按 Enter 預設全選: "
                ).strip()

                if choice == "":
                    target_devices = devices
                else:
                    try:
                        indices = [int(x.strip()) for x in choice.split(",")]
                        target_devices = [devices[i] for i in indices]
                    except Exception:
                        print("[ERROR] 輸入格式錯誤，程式結束。")
                        return bots
            else:
                target_devices = devices

        device_list = [d.serial for d in target_devices]
        if from_gui:
            if "device_configs" not in _config.RUNNING_CONFIG:
                _config.RUNNING_CONFIG["device_configs"] = {}
            for device_id in device_list:
                if device_id not in _config.RUNNING_CONFIG["device_configs"]:
                    _config.RUNNING_CONFIG["device_configs"][device_id] = (
                        _config.RUNNING_CONFIG["energy_strategy"]
                    )
            log_device_configs(device_list)
        else:
            setup_device_configs(device_list)

        for d in target_devices:
            device_strategy = _config.RUNNING_CONFIG["device_configs"].get(
                d.serial, _config.RUNNING_CONFIG["energy_strategy"]
            )
            bot = DriftBot(
                mode="2",
                name=f"Emu-{d.serial}",
                device=d,
                device_config_strategy=device_strategy,
            )
            bots.append(bot)

    elif mode == "1":
        find_pc_game_windows()

        if not PC_WINDOWS:
            bot_log("ERROR", "找不到遊戲視窗")
            return bots

        target_hwnds = []
        if from_gui:
            target_hwnds = _config.RUNNING_CONFIG.get("target_windows", []) or []
            if not target_hwnds:
                target_hwnds = list(PC_WINDOWS.keys())
        else:
            target_hwnds = []

        if not from_gui and len(PC_WINDOWS) > 1:
            print(f"\n[DEVICE] 偵測到 {len(PC_WINDOWS)} 個遊戲視窗:")
            windows_list = list(PC_WINDOWS.items())
            for i, (hwnd, title) in enumerate(windows_list):
                print(f"[{i}] {title} (HWND: {hwnd})")
            choice = input(
                f"\n請選擇要控制的視窗 (0-{len(windows_list)-1}): "
            ).strip()
            try:
                idx = int(choice)
                if 0 <= idx < len(windows_list):
                    target_hwnds.append(windows_list[idx][0])
                else:
                    print("[ERROR] 輸入超出範圍")
                    return bots
            except Exception:
                print("[ERROR] 輸入格式錯誤")
                return bots
        elif not from_gui:
            target_hwnds = list(PC_WINDOWS.keys())

        # 建立裝置 ID 以對應設定檔
        device_ids = [f"PC-{hwnd}" for hwnd in target_hwnds]
        if from_gui:
            if "device_configs" not in _config.RUNNING_CONFIG:
                _config.RUNNING_CONFIG["device_configs"] = {}
            for device_id in device_ids:
                if device_id not in _config.RUNNING_CONFIG["device_configs"]:
                    _config.RUNNING_CONFIG["device_configs"][device_id] = (
                        _config.RUNNING_CONFIG["energy_strategy"]
                    )
            log_device_configs(device_ids)
        else:
            setup_device_configs(device_ids)

        import win32gui

        for hwnd in target_hwnds:
            win32gui.MoveWindow(hwnd, 100, 100, BASE_W, BASE_H, True)
            device_id = f"PC-{hwnd}"
            device_strategy = _config.RUNNING_CONFIG["device_configs"].get(
                device_id, _config.RUNNING_CONFIG["energy_strategy"]
            )
            bot = DriftBot(
                mode=mode,
                name=device_id,
                hwnd=hwnd,
                device_config_strategy=device_strategy,
            )
            bots.append(bot)
    else:
        bot_log("ERROR", "錯誤選擇")
        return bots

    load_templates()

    if not from_gui:
        print("\n" + "=" * 50)
        print(f"啟動共 {len(bots)} 個獨立控制執行緒...")
        print("=" * 50)
        print("\n[TIP] 執行中可使用 Ctrl+D / Ctrl+P 控制\n")

        set_cmd_input_enabled(True)
        listener_thread = threading.Thread(target=input_listener, daemon=True)
        listener_thread.start()
    else:
        listener_thread = None

    # 啟動所有 bot 線程
    for bot in bots:
        bot.daemon = True
        bot.start()

    if not from_gui:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[LOCK] 停止所有執行。")
            set_cmd_input_enabled(False)
            set_paused(False)
            for bot in bots:
                try:
                    bot.stop()
                except Exception:
                    pass
            for bot in bots:
                try:
                    bot.join(timeout=2)
                except Exception:
                    pass
            if listener_thread:
                try:
                    listener_thread.join(timeout=1)
                except Exception:
                    pass

    return bots


if __name__ == "__main__":
    main()
