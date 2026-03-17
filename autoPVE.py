import win32gui, win32ui, win32con, win32api
import cv2
import numpy as np
import time, os, ctypes, json, threading, subprocess, re, sys
import pydirectinput
from ppadb.client import Client as AdbClient
from copy import deepcopy
from collections import deque
from datetime import datetime
from queue import Queue, Empty

# 全局日誌隊列（需要與 main_gui.py 同步）
LOG_QUEUE = None
CMD_INPUT_ENABLED = True
RUNNING_FROM_GUI = False

def set_log_queue(queue):
    """設置日誌隊列"""
    global LOG_QUEUE
    LOG_QUEUE = queue

def set_cmd_input_enabled(enabled):
    """GUI 模式下禁用 cmd 輸入"""
    global CMD_INPUT_ENABLED
    CMD_INPUT_ENABLED = bool(enabled)

def set_debug_mode(enabled):
    """GUI/CLI 切換除錯模式"""
    global DEBUG_MODE
    with LOCK:
        DEBUG_MODE = bool(enabled)

def set_paused(enabled):
    """GUI/CLI 切換暫停狀態"""
    global PAUSED
    with LOCK:
        PAUSED = bool(enabled)

def bot_log(tag, message, level="INFO"):
    """
    統一的日誌函數
    Args:
        tag: 日誌標籤 (如 "START", "BATTLE", "ENERGY" 等)
        message: 日誌消息 (可以是直接字符串或從 STRINGS 中的 key)
        level: 日誌級別 (INFO, WARN, ERROR 等，默認 INFO)
    """
    timestamp = time.strftime("%H:%M:%S")
    log_msg = f"[{timestamp}] [{tag}] {message}"
    
    # 發送到隊列（供 GUI 使用）
    if LOG_QUEUE:
        try:
            LOG_QUEUE.put_nowait(log_msg)
        except:
            pass
    
    # 同時輸出到控制台（GUI 模式下避免重複）
    if not RUNNING_FROM_GUI:
        print(log_msg, flush=True)

# 設置 DPI 感知
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    ctypes.windll.user32.SetProcessDPIAware()

# ========== 多語言系統 ==========

LANGUAGE = "zh_TW"  # 可選: "zh_TW", "zh_CN", "en"

def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)

def load_localization(language="zh_TW"):
    """加載多語言配置"""
    try:
        with open(resource_path("localization.json"), "r", encoding="utf-8") as f:
            localization = json.load(f)
        return localization.get(language, localization["zh_TW"])
    except Exception as e:
        print(f"Failed to load localization: {e}")
        return {}

# 全局字符串對象
STRINGS = load_localization(LANGUAGE)

# --- 參數設定 ---
WINDOW_TITLE = "飄流幻境Re:星之方舟" 
THRESHOLD = 0.80 

# 【核心設定】基準解析度
BASE_W, BASE_H = 1275, 755 

CONFIG_FILE = "bot_config.json"

# 【統一配置結構】從 default_config.json 加載預設配置
def load_default_config():
    """從 default_config.json 加載預設配置"""
    try:
        with open(resource_path("default_config.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load default_config.json: {e}")
        # 如果加載失敗，返回硬編碼的預設值
        return {
            "wait_times": {
                "scan_interval": 1.0,
                "after_click": 0.1,
                "pop_window": 0.1,
                "battle_unlock": 1.0,
                "join_confirm": 0.1,
                "wait_battle_check": 30.0
            },
            "energy_strategy": False,
            "thresholds": {
                "PC": {
                    "title": 0.80, "btn_add": 0.80, "btn_confirm": 0.80,
                    "btn_join": 0.80, "in_battle": 0.80, "energy_low": 0.9, "energy_9": 0.92
                },
                "EMU": {
                    "title": 0.70, "btn_add": 0.70, "btn_confirm": 0.70,
                    "btn_join": 0.70, "in_battle": 0.70, "energy_low": 0.74, "energy_9": 0.88
                }
            },
            "device_configs": {}
        }

DEFAULT_CONFIG = load_default_config()
RUNNING_CONFIG = deepcopy(DEFAULT_CONFIG)

TEMPLATES_PATHS = {
    "title": "ref_main_title.png", "btn_add": "btn_add.png",
    "btn_confirm": "btn_confirm.png", "btn_join": "btn_join.png",
    "in_battle": "ref_in_battle.png", "energy_low": "ref_energy_low.png",
    "energy_9": "ref_energy_9.png"
}

LOADED_TEMPLATES = {}
DEBUG_MODE = True
PAUSED = False
LOCK = threading.Lock()
PC_WINDOWS = {}  # PC視窗緩存: {hwnd: window_title}

# --- 性能監測類 ---
class PerformanceMonitor:
    """監測每個 Bot 的性能指標"""
    def __init__(self, name, max_samples=100):
        self.name = name
        self.frame_times = deque(maxlen=max_samples)
        self.template_match_times = deque(maxlen=max_samples)
        self.screenshot_times = deque(maxlen=max_samples)
        self.last_report = time.time()
        self.report_interval = 10
        
    def log_frame(self, elapsed):
        self.frame_times.append(elapsed)
    def log_screenshot(self, elapsed):
        self.screenshot_times.append(elapsed)
    def log_template_match(self, elapsed):
        self.template_match_times.append(elapsed)
        
    def get_stats(self):
        if not self.frame_times:
            return None
        frame_avg = sum(self.frame_times) / len(self.frame_times)
        frame_fps = 1.0 / frame_avg if frame_avg > 0 else 0
        screenshot_avg = sum(self.screenshot_times) / len(self.screenshot_times) if self.screenshot_times else 0
        template_avg = sum(self.template_match_times) / len(self.template_match_times) if self.template_match_times else 0
        
        return {
            "fps": frame_fps,
            "frame_ms": frame_avg * 1000,
            "screenshot_ms": screenshot_avg * 1000,
            "template_ms": template_avg * 1000
        }
    
    def should_report(self):
        now = time.time()
        if now - self.last_report >= self.report_interval:
            self.last_report = now
            return True
        return False

def deep_update(d, u):
    """遞歸更新字典"""
    for k, v in u.items():
        if isinstance(v, dict):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d

# --- 共用功能函式 ---

def load_config():
    """統一的配置加載系統"""
    global RUNNING_CONFIG
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
            
            print("\n【已偵測到上次的配置】")
            print("─" * 50)
            print("等待時間設定：")
            for key, val in saved_config.get("wait_times", {}).items():
                default_val = DEFAULT_CONFIG["wait_times"][key]
                print(f"  {key:20} = {val:6.1f} (預設 {default_val:6.1f})")
            
            print("\n活力策略設定：")
            strategy_str = "停止等待" if saved_config.get("energy_strategy", False) else "自動回復"
            default_str = "停止等待" if DEFAULT_CONFIG["energy_strategy"] else "自動回復"
            print(f"  低活力時         = {strategy_str:8} (預設 {default_str})")
            print("─" * 50)
            
            ans = input("\n是否套用上次的配置？(Y/n): ").strip().lower()
            if ans != 'n':
                RUNNING_CONFIG = deepcopy(DEFAULT_CONFIG)
                RUNNING_CONFIG.update(saved_config)
                print("[OK] 已套用上次的配置！")
                return True
        except Exception as e:
            print(f"[WARN] 讀取配置異常: {e}")
    
    print("\n【開始設定配置】")
    print("=" * 50)
    
    print("\n1. 等待時間設定")
    print("   (掃描間隔、點擊後等待、彈窗等待、戰鬥解鎖、確認等待、等待戰鬥檢查)")
    ans = input("   是否自訂？(Y/n): ").strip().lower()
    if ans != 'n':
        print("\n【等待時間設定】")
        for key in RUNNING_CONFIG["wait_times"].keys():
            default_val = DEFAULT_CONFIG["wait_times"][key]
            new_val = input(f"  {key:20} (預設 {default_val}): ").strip()
            if new_val:
                try:
                    RUNNING_CONFIG["wait_times"][key] = float(new_val)
                except:
                    RUNNING_CONFIG["wait_times"][key] = default_val
    
    print("\n2. 分數門檻設定")
    print("   (PC版和EMU版分別設定)")
    ans = input("   是否自訂？(y/N): ").strip().lower()
    if ans == 'y':
        for platform in ["PC", "EMU"]:
            print(f"\n【{platform} 版本】")
            for key in DEFAULT_CONFIG["thresholds"][platform].keys():
                default_val = DEFAULT_CONFIG["thresholds"][platform][key]
                new_val = input(f"  {key:15} (預設 {default_val:.2f}): ").strip()
                if new_val:
                    try:
                        RUNNING_CONFIG["thresholds"][platform][key] = float(new_val)
                    except:
                        RUNNING_CONFIG["thresholds"][platform][key] = default_val
    
    print("\n3. 活力策略設定")
    print("   低活力時的行動方式")
    ans = input("   是否自訂？(y/N): ").strip().lower()
    if ans == 'y':
        print("\n   False (f) - 自動回復到滿 (預設)")
        print("   True  (t) - 停止流程，等待活力恢復")
        val = input("   請選擇 (f/t): ").strip().lower()
        if val in ['t', 'true']:
            RUNNING_CONFIG["energy_strategy"] = True
        else:
            RUNNING_CONFIG["energy_strategy"] = False
    
    print("\n[OK] 配置設定完成")
    print("=" * 50)
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(RUNNING_CONFIG, f, indent=4, ensure_ascii=False)
    print("[SAVE] 配置已儲存到 bot_config.json")
    
    return False

def setup_device_configs(target_devices):
    """設定設備特定的活力策略配置"""
    # 確保 device_configs 鍵存在
    if "device_configs" not in RUNNING_CONFIG:
        RUNNING_CONFIG["device_configs"] = {}
    
    if len(target_devices) <= 1:
        for device_id in target_devices:
            RUNNING_CONFIG["device_configs"][device_id] = RUNNING_CONFIG["energy_strategy"]
        return
    
    ans = input(f"\n多設備偵測 ({len(target_devices)} 台)，是否為每台設備分別配置活力策略？(y/N): ").strip().lower()
    if ans == 'y':
        print("\n【設備活力策略配置】")
        for device_id in target_devices:
            print(f"\n[DEVICE] {device_id}")
            print(f"   (預設: {RUNNING_CONFIG['energy_strategy']})")
            val = input(f"   低活力時是否停止？(y/N): ").strip().lower()
            RUNNING_CONFIG["device_configs"][device_id] = (val == 'y')
    else:
        for device_id in target_devices:
            RUNNING_CONFIG["device_configs"][device_id] = RUNNING_CONFIG["energy_strategy"]

def log_device_configs(device_ids):
    """GUI 模式下將每台設備的活力策略顯示到 UI 日誌"""
    for device_id in device_ids:
        strategy = RUNNING_CONFIG["device_configs"].get(device_id, RUNNING_CONFIG["energy_strategy"])
        strategy_text = "停止等待" if strategy else "自動回復"
        bot_log("CONFIG", f"{device_id} 活力策略: {strategy_text}")

def load_templates():
    """載入共用模板"""
    global LOADED_TEMPLATES
    LOADED_TEMPLATES = {}
    folder = resource_path("templates")
    if not os.path.exists(folder):
        folder = os.path.join(os.path.abspath("."), "templates")
    bot_log("FOLDER", f"正在載入 {folder} 資料夾內的模板...")

    if not os.path.exists(folder):
        os.makedirs(folder)
        bot_log("WARN", f"找不到 {folder} 資料夾，已自動建立。請放入截圖！")

    for key, filename in TEMPLATES_PATHS.items():
        path = os.path.join(folder, filename)
        if os.path.exists(path):
            img = cv2.imread(path)
            if img is not None:
                LOADED_TEMPLATES[key] = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                bot_log("OK", f"成功載入: {filename}")
        else:
            bot_log("ERROR", f"缺檔: {path}")

def find_pc_game_windows():
    """搜尋所有 PC 遊戲視窗"""
    PC_WINDOWS.clear()
    
    def enum_windows(hwnd, lParam):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and len(title) > 0 and WINDOW_TITLE in title:
                PC_WINDOWS[hwnd] = title
        return True
    
    win32gui.EnumWindows(enum_windows, None)
    return PC_WINDOWS

def input_listener():
    """監聽控制台輸入"""
    global DEBUG_MODE, PAUSED
    if not CMD_INPUT_ENABLED:
        return
    while True:
        try:
            cmd = input().strip().lower()
            if cmd == "d":
                with LOCK:
                    DEBUG_MODE = not DEBUG_MODE
                state = "開啟" if DEBUG_MODE else "關閉"
                bot_log("DBG", f"除錯模式 {state}")
            elif cmd == "p":
                with LOCK:
                    PAUSED = not PAUSED
                state = "已暫停" if PAUSED else "已繼續"
                bot_log("PAUSE", state)
            elif cmd == "":
                continue
            else:
                bot_log("?", "未知指令，支援: d(debug)、p(pause)")
        except:
            pass

def connect_adb():
    """連接ADB並獲取所有設備"""
    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        devices = client.devices()
        if not devices:
            bot_log("ERROR", "找不到任何模擬器，請確認 ADB 是否啟動或模擬器『USB偵錯』已開。")
            return []
        return devices
    except Exception as e:
        bot_log("ERROR", f"ADB 連接異常: {e}")
        return []

# --- 機器人執行緒類別 ---

LDPLAYER_CONSOLE_CACHE = {"path": None, "instances": None, "ts": 0.0}

def find_ldplayer_console_path():
    candidates = [
        os.environ.get("LDPLAYER_CONSOLE", ""),
        r"C:\LDPlayer\LDPlayer9\dnconsole.exe",
        r"C:\LDPlayer\LDPlayer9\ldconsole.exe",
        r"C:\Program Files\LDPlayer\LDPlayer9\dnconsole.exe",
        r"C:\Program Files\LDPlayer\LDPlayer9\ldconsole.exe",
        r"C:\Program Files (x86)\LDPlayer\LDPlayer9\dnconsole.exe",
        r"C:\Program Files (x86)\LDPlayer\LDPlayer9\ldconsole.exe"
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None

def get_ldplayer_custom_names(console_path):
    """
    透過雷電控制台取得所有模擬器的自訂名稱與索引映射
    console_path: dnconsole.exe 或 ldconsole.exe 路徑
    """
    try:
        result = subprocess.check_output([console_path, "list2"], encoding="gbk", errors="ignore")
        instances = []
        for line in result.strip().split('\n'):
            if not line:
                continue
            data = line.split(',')
            if len(data) >= 2:
                instances.append({
                    "index": data[0].strip(),
                    "name": data[1].strip()
                })
        return instances
    except Exception:
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
    index_to_name = {inst.get("index"): inst.get("name") for inst in instances if inst.get("index") is not None}

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
    """取得模擬器自訂名稱"""
    serial = getattr(device, "serial", None)
    ld_name = get_ldplayer_custom_name_by_serial(serial)
    if ld_name:
        return ld_name
    if not hasattr(device, "shell"):
        return None
    settings_cmds = [
        "settings get global device_name",
        "settings get secure device_name",
        "settings get system device_name",
        "settings get secure bluetooth_name",
        "settings get system bluetooth_name"
    ]
    for cmd in settings_cmds:
        try:
            value = device.shell(cmd).strip()
        except Exception:
            value = ""
        if value and value.lower() not in {"null", "unknown", "generic"}:
            return value
    prop_keys = [
        "ro.boot.qemu.avd_name",
        "ro.kernel.qemu.avd_name",
        "ro.boot.avd_name",
        "persist.sys.display_name",
        "persist.sys.device_name"
    ]
    for prop in prop_keys:
        try:
            value = device.shell(f"getprop {prop}").strip()
        except Exception:
            value = ""
        if value and value.lower() not in {"unknown", "generic"}:
            return value
    return None

def get_device_model_name(device):
    """??璅⊥??蝔? (敺)?"""
    if not hasattr(device, "shell"):
        return None
    prop_keys = [
        "ro.product.model",
        "ro.product.marketname",
        "ro.product.device",
        "ro.product.name"
    ]
    for prop in prop_keys:
        try:
            value = device.shell(f"getprop {prop}").strip()
        except Exception:
            value = ""
        if value and value.lower() not in {"unknown", "generic"}:
            return value
    return None

def get_device_display_name(device):
    """顯示名稱: 自訂名稱(serial)"""
    serial = getattr(device, "serial", str(device))
    custom_name = get_device_custom_name(device)
    if custom_name:
        return f"{custom_name}({serial})"
    model_name = get_device_model_name(device)
    if model_name:
        return f"{model_name}({serial})"
    return serial

class DriftBot(threading.Thread):
    def __init__(self, mode, name, device=None, hwnd=None, device_config_strategy=None):
        super().__init__()
        # mode: "1" = PC, "2" = EMU
        self.mode = mode 
        self.name = name
        self.device = device
        self.hwnd = hwnd
        self.running = True
        self.waiting_for_battle = False
        self.wait_battle_start_time = 0
        
        self.real_w = BASE_W
        self.real_h = BASE_H
        
        platform = "PC" if mode == "1" else "EMU"
        self.thresholds = RUNNING_CONFIG["thresholds"][platform]
        self.stop_on_low_energy = device_config_strategy if device_config_strategy is not None else RUNNING_CONFIG["energy_strategy"]
        self.last_energy_state = None
        
        self.perf_monitor = PerformanceMonitor(name)
        self.last_screenshot = None
        self.last_screenshot_time = 0
        self.screenshot_cache_timeout = 0.05
        

    def stop(self):
        """停止線程"""
        self.running = False

    def log(self, msg):
        """統一的日誌方法"""
        bot_log(self.name, msg)

    def get_screenshot(self, use_cache=True):
        """獲取畫面，支援緩存"""
        start_time = time.time()
        
        if use_cache and self.last_screenshot is not None:
            cache_age = time.time() - self.last_screenshot_time
            if cache_age < self.screenshot_cache_timeout:
                return self.last_screenshot
        
        img = None
        if self.mode == "2":  # EMU
            try:
                image_bytes = self.device.screencap()
                img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
            except:
                img = None
        else:  # PC
            try:
                left, top, right, bot = win32gui.GetWindowRect(self.hwnd)
                self.real_w, self.real_h = right - left, bot - top
                hwndDC = win32gui.GetWindowDC(self.hwnd)
                mfcDC = win32ui.CreateDCFromHandle(hwndDC)
                saveDC = mfcDC.CreateCompatibleDC()
                saveBitMap = win32ui.CreateBitmap()
                saveBitMap.CreateCompatibleBitmap(mfcDC, self.real_w, self.real_h)
                saveDC.SelectObject(saveBitMap)
                ctypes.windll.user32.PrintWindow(self.hwnd, saveDC.GetSafeHdc(), 3)
                bmpstr = saveBitMap.GetBitmapBits(True)
                img = np.frombuffer(bmpstr, dtype='uint8').reshape((self.real_h, self.real_w, 4))
                
                win32gui.DeleteObject(saveBitMap.GetHandle())
                saveDC.DeleteDC()
                mfcDC.DeleteDC()
                win32gui.ReleaseDC(self.hwnd, hwndDC)
                
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            except:
                img = None
        
        if img is not None:
            self.last_screenshot = img
            self.last_screenshot_time = time.time()
        
        elapsed = time.time() - start_time
        self.perf_monitor.log_screenshot(elapsed)
        return img

    def execute_click(self, x, y):
        """動態座標映射與點擊執行"""
        real_x = int(x * (self.real_w / BASE_W))
        real_y = int(y * (self.real_h / BASE_H))

        if self.mode == "2":
            # 模擬器：ADB 點擊
            self.device.shell(f"input tap {real_x} {real_y}")
        else:
            # PC 模式：使用 pydirectinput 點擊
            client_point = win32gui.ClientToScreen(self.hwnd, (0, 0))
            pydirectinput.click(client_point[0] + real_x, client_point[1] + real_y)

    def find_pos(self, screen, key, custom_threshold=None):
        """多尺度模板匹配"""
        if key not in LOADED_TEMPLATES or screen is None or not isinstance(screen, np.ndarray):
            return None
        
        start_time = time.time()
        real_h, real_w = screen.shape[:2]
        
        gray_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        gray_screen = cv2.equalizeHist(gray_screen)
        
        scale_w = real_w / BASE_W
        template = LOADED_TEMPLATES[key]
        
        best_val = 0
        best_loc = None
        best_tpl_h, best_tpl_w = 0, 0
        
        scales = [scale_w * (1 + offset * 0.05) for offset in [-2, -1, 0, 1, 2]]
        
        for scale in scales:
            if scale <= 0:
                continue
            resized_tpl = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
            if resized_tpl.shape[0] > gray_screen.shape[0] or resized_tpl.shape[1] > gray_screen.shape[1]:
                continue
            
            res = cv2.matchTemplate(gray_screen, resized_tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            
            if max_val > best_val:
                best_val = max_val
                best_loc = max_loc
                best_tpl_h, best_tpl_w = resized_tpl.shape[:2]

        thresh = custom_threshold if custom_threshold else self.thresholds.get(key, 0.75)
        elapsed = time.time() - start_time
        self.perf_monitor.log_template_match(elapsed)
        
        if DEBUG_MODE and best_val >= 0.5 and key != "in_battle":
            self.log(f"[SEARCH] {key:12} | 分數: {best_val:.4f} | 門檻: {thresh:.2f} | 耗時: {elapsed*1000:.1f}ms")

        if best_val >= thresh and best_loc is not None:
            return (best_loc[0] + best_tpl_w // 2, best_loc[1] + best_tpl_h // 2)
        return None

    def run(self):
        self.log("[START] 開始執行循環...")
        
        while self.running:
            frame_start = time.time()
            
            try:
                # 檢查暫停狀態
                with LOCK:
                    if PAUSED:
                        time.sleep(0.5)
                        continue
                
                # 獲取截圖
                screen = self.get_screenshot(use_cache=False)
                if screen is None or not isinstance(screen, np.ndarray):
                    time.sleep(1)
                    continue

                # 偵測是否在戰鬥中
                if self.find_pos(screen, "in_battle"):
                    if self.waiting_for_battle:
                        self.log("[BATTLE] 戰鬥開始，解除鎖定。")
                        self.waiting_for_battle = False
                        self.last_energy_state = None
                    time.sleep(RUNNING_CONFIG["wait_times"]["battle_unlock"])
                    continue

                # 30秒檢查機制
                if self.waiting_for_battle:
                    elapsed_wait = time.time() - self.wait_battle_start_time
                    if elapsed_wait >= RUNNING_CONFIG["wait_times"]["wait_battle_check"]:
                        self.log("[TIME] 30秒檢查：確認是否進入戰鬥...")
                        check_screen = self.get_screenshot(use_cache=False)
                        
                        if check_screen is not None and isinstance(check_screen, np.ndarray):
                            if self.find_pos(check_screen, "in_battle"):
                                continue
                            
                            if self.find_pos(check_screen, "btn_join"):
                                self.log("[WARN] 搜尋超時，搜尋對手按鈕仍存在，重新執行搜尋...")
                                self.waiting_for_battle = False
                                self.wait_battle_start_time = 0
                            else:
                                self.log("[WAIT] 搜尋對手按鈕已消失，繼續等待...")
                                self.wait_battle_start_time = time.time()
                        
                        continue
                    else:
                        time.sleep(RUNNING_CONFIG["wait_times"]["scan_interval"])
                        continue

                # 確認在準備介面
                if self.find_pos(screen, "title"):
                    
                    # 活力補充流程
                    if self.find_pos(screen, "energy_low", self.thresholds.get("energy_low")):
                        if self.last_energy_state != "low":
                            self.last_energy_state = "low"
                            if self.stop_on_low_energy:
                                self.log("[ENERGY] 偵測到活力過低，根據設定停止流程。")
                            else:
                                self.log("[ENERGY] 偵測到活力過低，開始連續回復...")
                        
                        if self.stop_on_low_energy:
                            time.sleep(RUNNING_CONFIG["wait_times"]["scan_interval"])
                            continue
                        
                        safe_counter = 0
                        while safe_counter < 9:
                            scr_energy = self.get_screenshot(use_cache=False)
                            if scr_energy is None:
                                break
                                
                            if self.find_pos(scr_energy, "energy_9", self.thresholds.get("energy_9")):
                                break
                            
                            pos_add = self.find_pos(scr_energy, "btn_add")
                            if pos_add:
                                self.execute_click(pos_add[0], pos_add[1])
                                time.sleep(RUNNING_CONFIG["wait_times"]["pop_window"])
                                
                                scr_confirm = self.get_screenshot(use_cache=False)
                                pos_conf = self.find_pos(scr_confirm, "btn_confirm") if scr_confirm is not None else None
                                if pos_conf:
                                    self.execute_click(pos_conf[0], pos_conf[1])
                                    time.sleep(RUNNING_CONFIG["wait_times"]["after_click"])
                            
                            safe_counter += 1
                            time.sleep(0.3)
                        
                        self.last_energy_state = "normal"
                        self.log("[OK] 活力已達標或結束回復流程。")
                    else:
                        if self.last_energy_state == "low":
                            self.last_energy_state = "normal"
                            self.log("[ENERGY] 活力已恢復！")

                    # 搜尋對手流程
                    scr_match = self.get_screenshot(use_cache=False)
                    pos_join = self.find_pos(scr_match, "btn_join") if scr_match is not None else None
                    if pos_join:
                        self.log("[CLICK] 點擊搜尋對手...")
                        self.execute_click(pos_join[0], pos_join[1])
                        time.sleep(RUNNING_CONFIG["wait_times"]["join_confirm"])
                        
                        scr_final = self.get_screenshot(use_cache=False)
                        pos_final = self.find_pos(scr_final, "btn_confirm") if scr_final is not None else None
                        
                        if pos_final:
                            self.log("[OK] 出現確認視窗，點擊確認。")
                            self.execute_click(pos_final[0], pos_final[1])
                        else:
                            self.log("[SKIP] 無確認視窗，直接進入等待。")
                            
                        self.waiting_for_battle = True
                        self.wait_battle_start_time = time.time()
                        self.log("[LOCK] 進入等待開戰鎖定。")

                # 記錄幀耗時
                frame_elapsed = time.time() - frame_start
                self.perf_monitor.log_frame(frame_elapsed)
                
                if DEBUG_MODE and self.perf_monitor.should_report():
                    stats = self.perf_monitor.get_stats()
                    if stats:
                        self.log(f"[STAT] FPS: {stats['fps']:.1f} | 幀耗時: {stats['frame_ms']:.1f}ms | "
                                f"截圖: {stats['screenshot_ms']:.1f}ms | 匹配: {stats['template_ms']:.1f}ms")
                
                time.sleep(RUNNING_CONFIG["wait_times"]["scan_interval"])
            except Exception as e:
                self.log(f"[ERROR] {e}")
                time.sleep(2)

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
    # 如果從 GUI 啟動，使用 GUI 提供的配置
    global RUNNING_CONFIG, RUNNING_FROM_GUI
    RUNNING_FROM_GUI = bool(from_gui)
    if from_gui and config_override:
        # 使用 deep_update 合併配置，而不是完全替換
        RUNNING_CONFIG = deep_update(deepcopy(DEFAULT_CONFIG), config_override)
    elif not from_gui:
        # 維持原有的命令行加載邏輯
        load_config()

    if not from_gui:
        # ===== 命令行交互模式 =====
        print("="*50)
        print("  女王化身為無情的戰爭機器 小助手")
        print("="*50)
        print("【執行模式】")
        print("1. [PC 模式]     (只能單開，使用 pydirectinput)")
        print("2. [模擬器模式]  (支援多開，背景執行，使用 ADB)")
        print("\n【控制台指令】(執行中可輸入)")
        print("d       - 開啟/關閉除錯模式")
        print("p       - 暫停/繼續偵測")
        print("Ctrl+C  - 停止腳本")
        print("="*50)
        if mode_override:
            mode = mode_override
            mode_name = "PC 模式" if mode == "1" else "模擬器模式"
            print(f"\n[INFO] 已預設模式: {mode_name}")
        else:
            mode = input("\n請選擇模式 (1/2): ").strip()
    else:
        # ===== GUI 模式：使用提供的配置 =====
        mode = RUNNING_CONFIG.get("mode", "2")
    
    bots = []
    target_devices = []

    if mode == "2":
        # GUI 模式下，直接使用傳入的設備
        if from_gui:
            target_devices = RUNNING_CONFIG.get('target_devices', [])
            if not target_devices:
                 bot_log("DEVICE", "GUI模式下未選擇任何設備。")
                 return bots
        else:
            devices = connect_adb()
            if not devices:
                bot_log("DEVICE", "找不到任何模擬器，請確認 ADB 是否啟動或模擬器『USB偵錯』已開。")
                return bots
            
            if len(devices) > 1:
                print("\n[DEVICE] 偵測到多台設備:")
                for i, d in enumerate(devices):
                    print(f"[{i}] {get_device_display_name(d)}")
                choice = input("\n請輸入要執行的設備編號 (用逗號分隔，例如 0,1)。\n直接按 Enter 預設全選: ").strip()
                
                if choice == "":
                    target_devices = devices
                else:
                    try:
                        indices = [int(x.strip()) for x in choice.split(',')]
                        target_devices = [devices[i] for i in indices]
                    except:
                        print("[ERROR] 輸入格式錯誤，程式結束。")
                        return bots
            else:
                target_devices = devices
        
        device_list = [d.serial for d in target_devices]
        # 為 GUI 模式也執行設備配置
        if from_gui:
            if "device_configs" not in RUNNING_CONFIG:
                RUNNING_CONFIG["device_configs"] = {}
            for device_id in device_list:
                if device_id not in RUNNING_CONFIG["device_configs"]:
                    RUNNING_CONFIG["device_configs"][device_id] = RUNNING_CONFIG["energy_strategy"]
            log_device_configs(device_list)
        else:
            setup_device_configs(device_list)
        
        for d in target_devices:
            device_strategy = RUNNING_CONFIG["device_configs"].get(d.serial, RUNNING_CONFIG["energy_strategy"])
            bot = DriftBot(mode="2", name=f"Emu-{d.serial}", device=d, device_config_strategy=device_strategy)
            bots.append(bot)

    elif mode == "1":
        find_pc_game_windows()
        
        if not PC_WINDOWS:
            bot_log("ERROR", "找不到遊戲視窗")
            return bots
        
        target_hwnds = []
        if from_gui:
            target_hwnds = RUNNING_CONFIG.get("target_windows", []) or []
            if not target_hwnds:
                target_hwnds = list(PC_WINDOWS.keys())
        else:
            target_hwnds = []
        
        if not from_gui and len(PC_WINDOWS) > 1:
            print(f"\n[DEVICE] 偵測到 {len(PC_WINDOWS)} 個遊戲視窗:")
            windows_list = list(PC_WINDOWS.items())
            for i, (hwnd, title) in enumerate(windows_list):
                print(f"[{i}] {title} (HWND: {hwnd})")
            choice = input(f"\n請選擇要控制的視窗 (0-{len(windows_list)-1}): ").strip()
            try:
                idx = int(choice)
                if 0 <= idx < len(windows_list):
                    target_hwnds.append(windows_list[idx][0])
                else:
                    print("[ERROR] 輸入超出範圍")
                    return bots
            except:
                print("[ERROR] 輸入格式錯誤")
                return bots
        elif not from_gui:
            # 只有一個視窗或 GUI 模式時全選
            target_hwnds = list(PC_WINDOWS.keys())
            
            

        # 建立裝置 ID 以對應設定檔
        device_ids = [f"PC-{hwnd}" for hwnd in target_hwnds]
        if from_gui:
            if "device_configs" not in RUNNING_CONFIG:
                RUNNING_CONFIG["device_configs"] = {}
            for device_id in device_ids:
                if device_id not in RUNNING_CONFIG["device_configs"]:
                    RUNNING_CONFIG["device_configs"][device_id] = RUNNING_CONFIG["energy_strategy"]
            log_device_configs(device_ids)
        else:
            setup_device_configs(device_ids)
        
        # 為選定的每個視窗啟動一個 Bot
        for hwnd in target_hwnds:
            win32gui.MoveWindow(hwnd, 100, 100, BASE_W, BASE_H, True)
            device_id = f"PC-{hwnd}"
            device_strategy = RUNNING_CONFIG["device_configs"].get(device_id, RUNNING_CONFIG["energy_strategy"])
            bot = DriftBot(mode=mode, name=device_id, hwnd=hwnd, device_config_strategy=device_strategy)
            bots.append(bot)
    else:
        bot_log("ERROR", "錯誤選擇")
        return bots

    load_templates()

    if not from_gui:
        print("\n" + "="*50)
        print(f"啟動共 {len(bots)} 個獨立控制執行緒...")
        print("="*50)
        print("\n[TIP] 在下方輸入 'd' 或 'p' 來控制\n")

        listener_thread = threading.Thread(target=input_listener, daemon=True)
        listener_thread.start()

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
    
    return bots

if __name__ == "__main__":
    main()
