"""
PC 模式窗口管理器
用於檢測和管理遊戲窗口
"""

import win32gui
import win32ui
from typing import Dict, Tuple, Optional

class WindowManager:
    """PC窗口管理"""
    
    def __init__(self, window_title: str = "飄流幻境Re:星之方舟"):
        """
        初始化窗口管理器
        Args:
            window_title: 遊戲窗口標題（支持模糊匹配）
        """
        self.window_title = window_title
        self.windows = {}  # hwnd -> title 映射
        
    def find_windows(self) -> Dict[int, str]:
        """查找所有遊戲窗口"""
        self.windows.clear()
        
        try:
            import win32process
            import psutil
        except ImportError:
            win32process = None
            psutil = None

        def enum_windows(hwnd, lParam):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and len(title) > 0:
                    if win32process and psutil:
                        try:
                            from core.constants import GAME_EXE_NAME
                            _, pid = win32process.GetWindowThreadProcessId(hwnd)
                            process = psutil.Process(pid)
                            exe_name = process.name()
                            if GAME_EXE_NAME.lower() in exe_name.lower() or "main.exe" in exe_name.lower():
                                self.windows[hwnd] = title
                        except Exception:
                            pass
                    else:
                        if self.window_title in title:
                            self.windows[hwnd] = title
            return True
        
        try:
            win32gui.EnumWindows(enum_windows, None)
        except Exception as e:
            print(f"[ERROR] 枚舉窗口失敗: {e}")
        
        return self.windows

    def get_window_rect(self, hwnd: int) -> Optional[Tuple[int, int, int, int]]:
        """獲取窗口矩形"""
        try:
            return win32gui.GetWindowRect(hwnd)
        except:
            return None

    def get_window_size(self, hwnd: int) -> Optional[Tuple[int, int]]:
        """獲取窗口大小"""
        rect = self.get_window_rect(hwnd)
        if rect:
            left, top, right, bottom = rect
            return (right - left, bottom - top)
        return None

    def set_window_size(self, hwnd: int, width: int, height: int) -> bool:
        """設置窗口大小"""
        try:
            win32gui.MoveWindow(hwnd, 100, 100, width, height, True)
            return True
        except Exception as e:
            print(f"[ERROR] 設置窗口大小失敗: {e}")
            return False

    def get_window_screenshot(self, hwnd: int):
        """獲取窗口截圖"""
        import numpy as np
        import cv2
        
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width, height = right - left, bottom - top
            
            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)
            
            import ctypes
            ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)
            
            bmpstr = saveBitMap.GetBitmapBits(True)
            img = np.frombuffer(bmpstr, dtype='uint8').reshape((height, width, 4))
            
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwndDC)
            
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            return img
        except Exception as e:
            print(f"[ERROR] 獲取截圖失敗: {e}")
            return None

    def move_window_to_foreground(self, hwnd: int) -> bool:
        """將窗口移到前景"""
        try:
            win32gui.SetForegroundWindow(hwnd)
            return True
        except:
            return False
