"""
執行時全域狀態與存取器
"""
import threading

DEBUG_MODE = True
PAUSED = False
LOCK = threading.Lock()

# PC 視窗快取: {hwnd: window_title}
PC_WINDOWS = {}


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
