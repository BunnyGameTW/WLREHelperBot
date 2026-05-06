"""
設備偵測與命名工具
包含: LDPlayer 偵測、ADB 連線、PC 視窗搜尋、裝置顯示名稱
"""
import os
import re
import subprocess
import time
import locale

import win32gui
from ppadb.client import Client as AdbClient

from .constants import WINDOW_TITLE
from .logger import bot_log
from . import logger as _logger
from .state import DEBUG_MODE, PAUSED, LOCK, PC_WINDOWS

# ---- LDPlayer 控制台快取 ----
LDPLAYER_CONSOLE_CACHE = {"path": None, "instances": None, "ts": 0.0}


def _decode_console_output(raw):
    """Decode console bytes robustly for Windows CJK locales."""
    if isinstance(raw, str):
        return raw
    if raw is None:
        return ""

    preferred = locale.getpreferredencoding(False) or "utf-8"
    # Priority: current system code page first, then common Windows CJK encodings.
    encodings = [preferred, "cp950", "big5", "gbk", "utf-8"]
    tried = set()
    for enc in encodings:
        if not enc or enc in tried:
            continue
        tried.add(enc)
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def find_ldplayer_console_path():
    # 優先使用 ldconsole.exe（部分版本 dnconsole 不支援 list2）
    # 搜尋多種可能的安裝位置（含非預設磁碟與非 LDPlayer9 子資料夾）
    env_path = os.environ.get("LDPLAYER_CONSOLE", "")
    if env_path and os.path.exists(env_path):
        return env_path

    # 嘗試從使用者配置讀取路徑
    try:
        config_path = "bot_config_emu.json"
        if os.path.exists(config_path):
            import json as _json
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = _json.load(f)
            ld_dir = cfg.get("emulator_paths", {}).get("ldplayer", "")
            if ld_dir:
                for exe in ["ldconsole.exe", "dnconsole.exe"]:
                    p = os.path.join(ld_dir, exe)
                    if os.path.exists(p):
                        return p
    except Exception:
        pass

    # 建立搜尋基礎路徑
    base_dirs = [
        r"C:\LDPlayer",
        r"D:\LDPlayer",
        r"E:\LDPlayer",
        r"C:\LDPlayer\LDPlayer9",
        r"D:\LDPlayer\LDPlayer9",
        r"C:\Program Files\LDPlayer\LDPlayer9",
        r"C:\Program Files (x86)\LDPlayer\LDPlayer9",
        r"C:\Program Files\LDPlayer",
        r"C:\Program Files (x86)\LDPlayer",
    ]
    exe_names = ["ldconsole.exe", "dnconsole.exe"]

    for base in base_dirs:
        for exe in exe_names:
            path = os.path.join(base, exe)
            if os.path.exists(path):
                return path
    return None


def get_ldplayer_custom_names(console_path):
    """透過雷電控制台取得所有模擬器的自訂名稱與索引映射"""
    # 先嘗試 list2（ldconsole 支援），若失敗再嘗試目錄下的另一個 exe
    for exe_path in [console_path]:
        try:
            result_bytes = subprocess.check_output([exe_path, "list2"], timeout=5)
            result = _decode_console_output(result_bytes)
            if not result or not result.strip():
                continue
            instances = []
            for line in result.strip().splitlines():
                if not line:
                    continue
                data = line.split(",")
                if len(data) >= 2:
                    instances.append({"index": data[0].strip(), "name": data[1].strip()})
            if instances:
                return instances
        except Exception:
            pass

    # 若 console_path 是 dnconsole.exe 且失敗，嘗試同目錄的 ldconsole.exe（反之亦然）
    parent = os.path.dirname(console_path)
    basename = os.path.basename(console_path).lower()
    alt_name = "ldconsole.exe" if "dnconsole" in basename else "dnconsole.exe"
    alt_path = os.path.join(parent, alt_name)
    if os.path.exists(alt_path):
        try:
            result_bytes = subprocess.check_output([alt_path, "list2"], timeout=5)
            result = _decode_console_output(result_bytes)
            if result and result.strip():
                instances = []
                for line in result.strip().splitlines():
                    if not line:
                        continue
                    data = line.split(",")
                    if len(data) >= 2:
                        instances.append({"index": data[0].strip(), "name": data[1].strip()})
                if instances:
                    return instances
        except Exception:
            pass
    return []


def get_ldplayer_instances():
    now = time.time()
    cached = LDPLAYER_CONSOLE_CACHE
    if cached["instances"] is not None and now - cached["ts"] < 3.0:
        return cached["instances"]
    console_path = cached["path"] or find_ldplayer_console_path()
    if not console_path:
        cached["instances"] = []
        cached["ts"] = now
        return []
    instances = get_ldplayer_custom_names(console_path)
    cached["path"] = console_path
    cached["instances"] = instances
    cached["ts"] = now
    return instances


def get_ldplayer_custom_name_by_serial(serial):
    if not serial:
        return None
    instances = get_ldplayer_instances()
    if not instances:
        return None
    index_to_name = {
        inst.get("index"): inst.get("name")
        for inst in instances
        if inst.get("index") is not None
    }

    idx_candidates = []
    match = re.match(r"^emulator-(\d+)$", str(serial))
    if match:
        port = int(match.group(1))
        if port >= 5554 and (port - 5554) % 2 == 0:
            idx_candidates.append((port - 5554) // 2)
    host_match = re.match(r"^[^:]+:(\d+)$", str(serial))
    if host_match:
        port = int(host_match.group(1))
        if port >= 5555 and (port - 5555) % 2 == 0:
            idx_candidates.append((port - 5555) // 2)

    for idx in idx_candidates:
        name = index_to_name.get(str(idx))
        if name:
            return name
    return None


def get_device_custom_name(device):
    """取得 LDPlayer 自訂名稱（實例名稱），其他模擬器不支援"""
    serial = getattr(device, "serial", None)
    return get_ldplayer_custom_name_by_serial(serial)


def get_device_model_name(device):
    if not hasattr(device, "shell"):
        return None
    prop_keys = [
        "ro.product.model",
        "ro.product.marketname",
        "ro.product.device",
        "ro.product.name",
    ]
    for prop in prop_keys:
        try:
            value = device.shell(f"getprop {prop}").strip()
        except Exception:
            value = ""
        if value and value.lower() not in {"unknown", "generic"}:
            return value
    return None


def is_ldplayer_device(serial):
    """判斷 serial 是否為 LDPlayer 設備（交叉比對 ldconsole 實例列表）"""
    match = re.match(r"^emulator-(\d+)$", str(serial))
    if not match:
        return False
    port = int(match.group(1))
    if port < 5554 or (port - 5554) % 2 != 0:
        return False
    idx = (port - 5554) // 2
    # 必須在 ldconsole list2 的實例中存在
    instances = get_ldplayer_instances()
    if not instances:
        # ldconsole 不可用時，僅靠格式判斷（寬鬆模式）
        return True
    return any(inst.get("index") == str(idx) for inst in instances)


def get_device_display_name(device):
    """顯示名稱: LDPlayer實例名(型號)(serial)"""
    serial = getattr(device, "serial", str(device))

    # 1. LDPlayer 自訂名稱（實例名）
    ld_name = get_ldplayer_custom_name_by_serial(serial)

    # 2. 手機型號
    model_name = get_device_model_name(device)

    # 組合顯示
    if ld_name and model_name:
        return f"{ld_name} ({model_name}) [{serial}]"
    if ld_name:
        return f"{ld_name} [{serial}]"
    if model_name:
        return f"{model_name} [{serial}]"
    return serial


# ---- PC 遊戲視窗搜尋 ----

def find_pc_game_windows():
    """搜尋所有 PC 遊戲視窗"""
    PC_WINDOWS.clear()

    try:
        import win32process
        import psutil
    except ImportError:
        win32process = None
        psutil = None

    def enum_windows(hwnd, _lParam):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and len(title) > 0:
                if win32process and psutil:
                    try:
                        from core.constants import GAME_EXE_NAME
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        process = psutil.Process(pid)
                        exe_name = process.name()
                        # Only judge by exe name to avoid matching web browsers with the same title
                        if GAME_EXE_NAME.lower() in exe_name.lower() or "main.exe" in exe_name.lower():
                            PC_WINDOWS[hwnd] = title
                    except Exception:
                        pass
                else:
                    # Fallback to title check only if we don't have psutil/win32process available
                    if WINDOW_TITLE in title:
                        PC_WINDOWS[hwnd] = title
        return True

    win32gui.EnumWindows(enum_windows, None)
    return PC_WINDOWS


# ---- ADB 連線 ----

def connect_adb(quiet=False):
    """連接 ADB 並獲取所有設備。

    quiet=True 時，遇到無設備不輸出錯誤日誌（供 GUI 掃描使用）。
    """
    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        devices = client.devices()
        if not devices:
            if not quiet:
                bot_log(
                    "ERROR",
                    "找不到任何模擬器，請確認 ADB 是否啟動或模擬器『USB偵錯』已開。",
                )
            return []
        return devices
    except Exception as e:
        bot_log("ERROR", f"ADB 連接異常: {e}")
        return []


# ---- 控制台輸入監聽 ----

def input_listener():
    """監聽控制台輸入（使用 Ctrl+D / Ctrl+P / Ctrl+C）"""
    from . import state as _state  # 延遲匯入避免循環

    if not _logger.CMD_INPUT_ENABLED:
        return

    try:
        import msvcrt
        import _thread
        last_pause_toggle = 0.0
        pause_toggle_cooldown = 0.25
        while _logger.CMD_INPUT_ENABLED:
            try:
                if not msvcrt.kbhit():
                    time.sleep(0.05)
                    continue
                ch = msvcrt.getch()
                if ch == b'\x03':  # Ctrl+C - 觸發主執行緒中斷
                    _thread.interrupt_main()
                if ch == b'\x04':  # Ctrl+D - 切換除錯模式
                    with _state.LOCK:
                        _state.DEBUG_MODE = not _state.DEBUG_MODE
                    state_str = "開啟" if _state.DEBUG_MODE else "關閉"
                    bot_log("DBG", f"除錯模式 {state_str}")
                elif ch == b'\x10':  # Ctrl+P - 暫停/繼續
                    now = time.time()
                    if now - last_pause_toggle < pause_toggle_cooldown:
                        continue
                    last_pause_toggle = now
                    with _state.LOCK:
                        _state.PAUSED = not _state.PAUSED
                    state_str = "已暫停" if _state.PAUSED else "已繼續"
                    bot_log("PAUSE", state_str)
                elif ch in (b'\x00', b'\xe0'):
                    # 延伸鍵（方向鍵等），消耗第二個位元組
                    msvcrt.getch()
            except Exception:
                pass
    except ImportError:
        # 非 Windows 備援：使用文字輸入
        while _logger.CMD_INPUT_ENABLED:
            try:
                cmd = input().strip().lower()
                if cmd == "d":
                    with _state.LOCK:
                        _state.DEBUG_MODE = not _state.DEBUG_MODE
                    state_str = "開啟" if _state.DEBUG_MODE else "關閉"
                    bot_log("DBG", f"除錯模式 {state_str}")
                elif cmd == "p":
                    with _state.LOCK:
                        _state.PAUSED = not _state.PAUSED
                    state_str = "已暫停" if _state.PAUSED else "已繼續"
                    bot_log("PAUSE", state_str)
                elif cmd == "":
                    continue
                else:
                    bot_log("?", "未知指令，支援: Ctrl+D(除錯)、Ctrl+P(暫停)")
            except Exception:
                pass
