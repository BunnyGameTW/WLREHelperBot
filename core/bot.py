"""
DriftBot - 自動對戰核心執行緒
負責截圖、模板匹配、點擊執行等主要戰鬥循環
"""
import threading
import time
import ctypes

import cv2
import numpy as np
import win32gui  # type: ignore[reportMissingImports]
import win32ui  # type: ignore[reportMissingImports]
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

    def __init__(self, mode, name, device=None, hwnd=None, device_config_strategy=None, device_auto_features=None):
        super().__init__()
        # mode: "1" = PC, "2" = EMU
        self.mode = mode
        self.name = name
        self.device = device
        self.hwnd = hwnd
        self.device_id = self._resolve_device_id()
        self.running = True
        self.waiting_for_battle = False
        self.wait_battle_start_time = 0

        self.real_w = BASE_W
        self.real_h = BASE_H

        platform = "PC" if mode == "1" else "EMU"
        self.platform = platform
        self.thresholds = _config.RUNNING_CONFIG["thresholds"][platform]
        self._device_config_strategy_override = device_config_strategy
        self.stop_on_low_energy = (
            device_config_strategy
            if device_config_strategy is not None
            else _config.RUNNING_CONFIG["energy_strategy"]
        )
        self.device_auto_features = device_auto_features  # {"wander": bool, "ai": bool} or None
        self.auto_battle_enabled = bool(_config.RUNNING_CONFIG.get("auto_battle_enabled", True))
        self.device_feature_overrides = None
        self.last_energy_state = None

        self.perf_monitor = PerformanceMonitor(name)
        self.last_screenshot = None
        self.last_screenshot_time = 0
        self.screenshot_cache_timeout = 0.05

        # 灰階影像快取：避免同一幀重複 cvtColor + equalizeHist
        self._gray_cache_id = None
        self._gray_cache_img = None

        # 斷線偵測處理器（預留接口）
        self.disconnect_handler = DisconnectHandler(bot=self)

        # hwnd 變更回調（供 GUI 更新視窗資訊）
        self.on_hwnd_changed = None

    def _resolve_device_id(self):
        """產生與設定檔一致的設備 ID。"""
        if self.mode == "2" and self.device is not None:
            serial = getattr(self.device, "serial", "")
            return str(serial or self.name)
        if self.mode == "1":
            hwnd = int(self.hwnd or 0)
            return f"PC-{hwnd}" if hwnd > 0 else str(self.name)
        return str(self.name)

    def refresh_runtime_config(self):
        """同步執行中的可熱更新設定（暫停修改後可直接套用）。"""
        try:
            cfg = _config.RUNNING_CONFIG
            self.thresholds = cfg.get("thresholds", {}).get(self.platform, self.thresholds)
            profile = cfg.get("device_feature_profiles", {}).get(self.device_id, {})
            if profile:
                self.device_feature_overrides = {
                    "disconnect_enabled": bool(profile.get("disconnect_enabled", True)),
                    "auto_enable_features_enabled": bool(profile.get("auto_enable_features_enabled", True)),
                    "scheduled_restart_enabled": bool(profile.get("scheduled_restart_enabled", False)),
                }
                self.auto_battle_enabled = bool(profile.get("auto_battle_enabled", self.auto_battle_enabled))
            else:
                self.device_feature_overrides = None
            if self.mode == "2" and self.device is not None:
                serial = getattr(self.device, "serial", None)
                per_device_strategy = cfg.get("device_configs", {}).get(serial)
                profile_strategy = profile.get("stop_on_low_energy") if profile else None
                if profile_strategy is not None:
                    self._device_config_strategy_override = bool(profile_strategy)
                    self.stop_on_low_energy = bool(profile_strategy)
                elif per_device_strategy is not None:
                    self._device_config_strategy_override = bool(per_device_strategy)
                    self.stop_on_low_energy = bool(per_device_strategy)
                elif self._device_config_strategy_override is None:
                    self.stop_on_low_energy = cfg.get("energy_strategy", self.stop_on_low_energy)

                # 每台設備自動開啟功能可在執行中熱更新。
                # DisconnectHandler 會優先讀取 bot.device_auto_features 作為覆寫來源，
                # 若不在此同步，暫停期間儲存後恢復仍會沿用舊值直到重啟。
                per_device_auto = cfg.get("device_auto_features", {}).get(serial)
                if per_device_auto is not None:
                    self.device_auto_features = {
                        "wander": bool(per_device_auto.get("wander", True)),
                        "ai": bool(per_device_auto.get("ai", True)),
                    }
                else:
                    self.device_auto_features = None
            elif self.mode == "1":
                profile_strategy = profile.get("stop_on_low_energy") if profile else None
                if profile_strategy is not None:
                    self._device_config_strategy_override = bool(profile_strategy)
                    self.stop_on_low_energy = bool(profile_strategy)
                elif self._device_config_strategy_override is None:
                    self.stop_on_low_energy = cfg.get("energy_strategy", self.stop_on_low_energy)

            if not profile:
                self.auto_battle_enabled = bool(cfg.get("auto_battle_enabled", self.auto_battle_enabled))
            if self.disconnect_handler is not None:
                self.disconnect_handler.refresh_config()
        except Exception as e:
            self.log(f"[WARN] 刷新執行中設定失敗: {e}")

    def _clear_frame_cache(self):
        """釋放影像快取，降低長時間運行後的記憶體占用。"""
        self.last_screenshot = None
        self._gray_cache_id = None
        self._gray_cache_img = None

    def _is_complete_png_bytes(self, data):
        """快速檢查 PNG bytes 是否完整（至少包含合法 IEND chunk）。"""
        if not data or len(data) < 8:
            return False
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            return False

        offset = 8
        size = len(data)
        while offset + 8 <= size:
            length = int.from_bytes(data[offset:offset + 4], "big", signed=False)
            chunk_type = data[offset + 4:offset + 8]
            offset += 8

            if offset + length + 4 > size:
                return False

            offset += length + 4
            if chunk_type == b"IEND":
                return True

        return False

    def stop(self):
        """停止線程"""
        self.running = False
        self._clear_frame_cache()

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

                # screencap 偶發回傳不完整 PNG，先檢查可避免 libpng 錯誤訊息。
                if self._is_complete_png_bytes(image_bytes):
                    img = cv2.imdecode(
                        np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR
                    )
                else:
                    # 立即重試一次，減少瞬間傳輸中斷造成的空幀。
                    retry_bytes = self.device.screencap()
                    if self._is_complete_png_bytes(retry_bytes):
                        img = cv2.imdecode(
                            np.frombuffer(retry_bytes, np.uint8), cv2.IMREAD_COLOR
                        )
                    else:
                        img = None
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

    def execute_key(self, key_name, android_keycode=None):
        """跨平台按鍵輸入。PC 使用 pydirectinput，EMU 使用 ADB keyevent。"""
        if self.mode == "2":
            if android_keycode is not None:
                self.device.shell(f"input keyevent {int(android_keycode)}")
                return
            key_map = {
                "esc": 111,
                "r": 46,
            }
            if key_name.lower() in key_map:
                self.device.shell(f"input keyevent {key_map[key_name.lower()]}")
            return

        pydirectinput.press(key_name)

    # ---- 模板匹配 ----

    def find_pos(self, screen, key, custom_threshold=None):
        """多尺度模板匹配"""
        if key not in LOADED_TEMPLATES or screen is None or not isinstance(screen, np.ndarray):
            return None

        start_time = time.time()
        real_h, real_w = screen.shape[:2]

        # 灰階影像快取：同一幀只做一次 cvtColor + equalizeHist
        screen_id = id(screen)
        if self._gray_cache_id == screen_id:
            gray_screen = self._gray_cache_img
        else:
            gray_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
            gray_screen = cv2.equalizeHist(gray_screen)
            self._gray_cache_id = screen_id
            self._gray_cache_img = gray_screen

        scale_w = real_w / BASE_W
        template = LOADED_TEMPLATES[key]

        best_val = 0
        best_loc = None
        best_tpl_h, best_tpl_w = 0, 0

        scales = [scale_w * (1 + offset * 0.05) for offset in [-1, 0, 1]]

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
            _t_now = time.time()
            _debug_times = getattr(self, '_debug_search_log_times', None)
            if _debug_times is None:
                self._debug_search_log_times = {}
                _debug_times = self._debug_search_log_times
            if _t_now - _debug_times.get(key, 0) >= 1.0:
                match_state = "HIT" if best_val >= thresh else "MISS"
                self.log(
                    f"[SEARCH] {key:12} | {match_state:4} | 分數: {best_val:.4f} | 門檻: {thresh:.2f} | 耗時: {elapsed*1000:.1f}ms"
                )
                _debug_times[key] = _t_now

        if best_val >= thresh and best_loc is not None:
            return (best_loc[0] + best_tpl_w // 2, best_loc[1] + best_tpl_h // 2)
        return None

    # ---- 主循環 ----

    def _interruptible_sleep(self, duration):
        """可中斷的 sleep，每 0.1 秒檢查 self.running。"""
        end = time.time() + duration
        while self.running and time.time() < end:
            time.sleep(min(0.1, end - time.time()))

    def run(self):
        self.log("[START] 開始執行循環...")

        while self.running:
            frame_start = time.time()

            try:
                # 檢查暫停狀態
                with _state.LOCK:
                    if _state.PAUSED:
                        self._interruptible_sleep(0.5)
                        continue

                # EMU 重連流程 A 的關閉/啟動/暖機步驟不依賴畫面；
                # 先推進 recovery，可避免 screencap 卡住導致流程停滯。
                if self.mode == "2" and self.disconnect_handler.should_skip_screen_capture():
                    if self.running and self.disconnect_handler.check(None):
                        self._interruptible_sleep(_config.RUNNING_CONFIG["wait_times"]["scan_interval"])
                        continue

                # 獲取截圖
                screen = self.get_screenshot(use_cache=False)
                if screen is None or not isinstance(screen, np.ndarray):
                    # EMU 在重連期間即使無畫面，也要讓斷線流程持續推進。
                    if self.running and self.disconnect_handler.check(None):
                        continue
                    # PC 模式若視窗被關閉，讓斷線處理器仍可驅動重啟流程。
                    if self.running and self.disconnect_handler.handle_missing_screen():
                        continue
                    self._interruptible_sleep(1)
                    continue

                # 【預留】斷線偵測 hook
                if self.running and self.disconnect_handler.check(screen):
                    continue

                if not self.running:
                    break

                # 偵測是否在戰鬥中
                if self.find_pos(screen, "in_battle"):
                    if self.waiting_for_battle:
                        self.log("[BATTLE] 戰鬥開始，解除鎖定。")
                        self.waiting_for_battle = False
                        self.last_energy_state = None
                    self._interruptible_sleep(_config.RUNNING_CONFIG["wait_times"]["battle_unlock"])
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
                        self._interruptible_sleep(_config.RUNNING_CONFIG["wait_times"]["scan_interval"])
                        continue

                # 自動玩家對戰停用時，略過 battle_title 偵測
                if self.auto_battle_enabled and self.find_pos(screen, "battle_title"):
                    should_search = self._handle_energy(screen)
                    if should_search:
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

                self._interruptible_sleep(_config.RUNNING_CONFIG["wait_times"]["scan_interval"])
            except Exception as e:
                self.log(f"[ERROR] {e}")
                self._interruptible_sleep(2)

        self._clear_frame_cache()

    # ---- 子流程 ----

    def _handle_energy(self, screen):
        """活力補充流程
        
        Returns:
            True: 可繼續搜尋對手
            False: 本輪不應搜尋（活力過低且需等待/補充中）
        """
        if self.find_pos(screen, "energy_low", self.thresholds.get("energy_low")):
            if self.last_energy_state != "low":
                self.last_energy_state = "low"
                if self.stop_on_low_energy:
                    self.log("[ENERGY] 偵測到活力過低，根據設定停止流程。")
                else:
                    self.log("[ENERGY] 偵測到活力過低，開始連續回復...")

            if self.stop_on_low_energy:
                time.sleep(_config.RUNNING_CONFIG["wait_times"]["scan_interval"])
                return False  # 停止搜尋

            safe_counter = 0
            recovered = False
            while safe_counter < 9:
                scr_energy = self.get_screenshot(use_cache=False)
                if scr_energy is None:
                    break

                if self.find_pos(scr_energy, "energy_9", self.thresholds.get("energy_9")):
                    recovered = True
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

            # 補充流程結束後再檢查一次，只有確認回到非低活力才允許繼續搜尋。
            final_screen = self.get_screenshot(use_cache=False)
            if final_screen is not None and not recovered:
                if self.find_pos(final_screen, "energy_9", self.thresholds.get("energy_9")):
                    recovered = True
            still_low = False
            if final_screen is not None:
                still_low = bool(self.find_pos(final_screen, "energy_low", self.thresholds.get("energy_low")))

            if recovered or not still_low:
                self.last_energy_state = "normal"
                self.log("[OK] 活力已達標，繼續搜尋。")
                return True

            self.last_energy_state = "low"
            self.log("[ENERGY] 活力仍不足，暫不搜尋對手，下一輪繼續補充。")
            return False
        else:
            if self.last_energy_state == "low":
                self.last_energy_state = "normal"
                self.log("[ENERGY] 活力已恢復！")
        
        return True  # 可继续搜尋

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
