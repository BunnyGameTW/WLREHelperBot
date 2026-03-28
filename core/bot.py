"""
DriftBot - 自動對戰核心執行緒
負責截圖、模板匹配、點擊執行等主要戰鬥循環
"""
import threading
import time
import ctypes

import cv2
import numpy as np
import win32gui
import win32ui
import pydirectinput

from .constants import BASE_W, BASE_H
from .logger import bot_log
from . import state as _state
from . import config as _config
from .templates import LOADED_TEMPLATES
from .performance import PerformanceMonitor
from .disconnect_handler import DisconnectHandler


class DriftBot(threading.Thread):
    """自動對戰機器人執行緒"""

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
        self.thresholds = _config.RUNNING_CONFIG["thresholds"][platform]
        self.stop_on_low_energy = (
            device_config_strategy
            if device_config_strategy is not None
            else _config.RUNNING_CONFIG["energy_strategy"]
        )
        self.last_energy_state = None

        self.perf_monitor = PerformanceMonitor(name)
        self.last_screenshot = None
        self.last_screenshot_time = 0
        self.screenshot_cache_timeout = 0.05

        # 斷線偵測處理器（預留接口）
        self.disconnect_handler = DisconnectHandler(bot=self)

    def stop(self):
        """停止線程"""
        self.running = False

    def log(self, msg):
        """統一的日誌方法"""
        bot_log(self.name, msg)

    # ---- 截圖 ----

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
                img = cv2.imdecode(
                    np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR
                )
            except Exception:
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
                img = np.frombuffer(bmpstr, dtype="uint8").reshape(
                    (self.real_h, self.real_w, 4)
                )

                win32gui.DeleteObject(saveBitMap.GetHandle())
                saveDC.DeleteDC()
                mfcDC.DeleteDC()
                win32gui.ReleaseDC(self.hwnd, hwndDC)

                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            except Exception:
                img = None

        if img is not None:
            self.last_screenshot = img
            self.last_screenshot_time = time.time()

        elapsed = time.time() - start_time
        self.perf_monitor.log_screenshot(elapsed)
        return img

    # ---- 點擊 ----

    def execute_click(self, x, y):
        """動態座標映射與點擊執行"""
        real_x = int(x * (self.real_w / BASE_W))
        real_y = int(y * (self.real_h / BASE_H))

        if self.mode == "2":
            self.device.shell(f"input tap {real_x} {real_y}")
        else:
            client_point = win32gui.ClientToScreen(self.hwnd, (0, 0))
            pydirectinput.click(client_point[0] + real_x, client_point[1] + real_y)

    # ---- 模板匹配 ----

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
            resized_tpl = cv2.resize(
                template, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR
            )
            if (
                resized_tpl.shape[0] > gray_screen.shape[0]
                or resized_tpl.shape[1] > gray_screen.shape[1]
            ):
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

        if _state.DEBUG_MODE and key != "in_battle":
            match_state = "HIT" if best_val >= thresh else "MISS"
            self.log(
                f"[SEARCH] {key:12} | {match_state:4} | 分數: {best_val:.4f} | 門檻: {thresh:.2f} | 耗時: {elapsed*1000:.1f}ms"
            )

        if best_val >= thresh and best_loc is not None:
            return (best_loc[0] + best_tpl_w // 2, best_loc[1] + best_tpl_h // 2)
        return None

    # ---- 主循環 ----

    def run(self):
        self.log("[START] 開始執行循環...")

        while self.running:
            frame_start = time.time()

            try:
                # 檢查暫停狀態
                with _state.LOCK:
                    if _state.PAUSED:
                        time.sleep(0.5)
                        continue

                # 獲取截圖
                screen = self.get_screenshot(use_cache=False)
                if screen is None or not isinstance(screen, np.ndarray):
                    time.sleep(1)
                    continue

                # 【預留】斷線偵測 hook
                if self.disconnect_handler.check(screen):
                    continue

                # 偵測是否在戰鬥中
                if self.find_pos(screen, "in_battle"):
                    if self.waiting_for_battle:
                        self.log("[BATTLE] 戰鬥開始，解除鎖定。")
                        self.waiting_for_battle = False
                        self.last_energy_state = None
                    time.sleep(_config.RUNNING_CONFIG["wait_times"]["battle_unlock"])
                    continue

                # 30 秒檢查機制
                if self.waiting_for_battle:
                    elapsed_wait = time.time() - self.wait_battle_start_time
                    if elapsed_wait >= _config.RUNNING_CONFIG["wait_times"]["wait_battle_check"]:
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
                        time.sleep(_config.RUNNING_CONFIG["wait_times"]["scan_interval"])
                        continue

                # 確認在準備介面
                if self.find_pos(screen, "title"):
                    self._handle_energy(screen)
                    self._handle_match_search()

                # 記錄幀耗時
                frame_elapsed = time.time() - frame_start
                self.perf_monitor.log_frame(frame_elapsed)

                if _state.DEBUG_MODE and self.perf_monitor.should_report():
                    stats = self.perf_monitor.get_stats()
                    if stats:
                        self.log(
                            f"[STAT] FPS: {stats['fps']:.1f} | 幀耗時: {stats['frame_ms']:.1f}ms | "
                            f"截圖: {stats['screenshot_ms']:.1f}ms | 匹配: {stats['template_ms']:.1f}ms"
                        )

                time.sleep(_config.RUNNING_CONFIG["wait_times"]["scan_interval"])
            except Exception as e:
                self.log(f"[ERROR] {e}")
                time.sleep(2)

    # ---- 子流程 ----

    def _handle_energy(self, screen):
        """活力補充流程"""
        if self.find_pos(screen, "energy_low", self.thresholds.get("energy_low")):
            if self.last_energy_state != "low":
                self.last_energy_state = "low"
                if self.stop_on_low_energy:
                    self.log("[ENERGY] 偵測到活力過低，根據設定停止流程。")
                else:
                    self.log("[ENERGY] 偵測到活力過低，開始連續回復...")

            if self.stop_on_low_energy:
                time.sleep(_config.RUNNING_CONFIG["wait_times"]["scan_interval"])
                return

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
                    time.sleep(_config.RUNNING_CONFIG["wait_times"]["pop_window"])

                    scr_confirm = self.get_screenshot(use_cache=False)
                    pos_conf = (
                        self.find_pos(scr_confirm, "btn_confirm")
                        if scr_confirm is not None
                        else None
                    )
                    if pos_conf:
                        self.execute_click(pos_conf[0], pos_conf[1])
                        time.sleep(_config.RUNNING_CONFIG["wait_times"]["after_click"])

                safe_counter += 1
                time.sleep(0.3)

            self.last_energy_state = "normal"
            self.log("[OK] 活力已達標或結束回復流程。")
        else:
            if self.last_energy_state == "low":
                self.last_energy_state = "normal"
                self.log("[ENERGY] 活力已恢復！")

    def _handle_match_search(self):
        """搜尋對手流程"""
        scr_match = self.get_screenshot(use_cache=False)
        pos_join = self.find_pos(scr_match, "btn_join") if scr_match is not None else None
        if pos_join:
            self.log("[CLICK] 點擊搜尋對手...")
            self.execute_click(pos_join[0], pos_join[1])
            time.sleep(_config.RUNNING_CONFIG["wait_times"]["join_confirm"])

            scr_final = self.get_screenshot(use_cache=False)
            pos_final = (
                self.find_pos(scr_final, "btn_confirm")
                if scr_final is not None
                else None
            )

            if pos_final:
                self.log("[OK] 出現確認視窗，點擊確認。")
                self.execute_click(pos_final[0], pos_final[1])
            else:
                self.log("[SKIP] 無確認視窗，直接進入等待。")

            self.waiting_for_battle = True
            self.wait_battle_start_time = time.time()
            self.log("[LOCK] 進入等待開戰鎖定。")
