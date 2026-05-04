"""
斷線偵測與重連處理。

支援場景:
  1) 網路斷線但無彈窗: 同畫面停滯超時
  2) 斷線彈窗 A: 直接重連
  3) 斷線彈窗 B: 返回登入後重新登入
  4) 臨時維修彈窗 C: 返回登入後重新登入

遊戲狀態機:
  - disconnect(1):  登入/斷線彈窗偵測
  - select_character(2): 角色選擇
  - in_game(3):     進遊戲彈窗處理
  - after_in_game(4): 遊戲中斷線監控

流程區塊:
  - 流程 A: 重開遊戲
  - 流程 B: 登入遊戲
  - 流程 C: 進遊戲後恢復狀態
"""

import os
import csv
import subprocess
import time
import ctypes

import cv2
import numpy as np

try:
    import win32gui  # type: ignore[reportMissingImports]
    import win32process  # type: ignore[reportMissingImports]
except Exception:
    win32gui = None
    win32process = None

from . import config as _config
from . import state as _state
from .device_utils import find_ldplayer_console_path
from .constants import RECONNECT_SERVER_CLICK_POINT, WINDOW_TITLE
from .disconnect_helpers import (
    can_act,
    click_point,
    click_template,
    extract_package_from_text,
    handle_post_login_popups,
    has_template,
    serial_to_ldplayer_index,
)

# 遊戲狀態常數
GAME_STATE_DISCONNECT = 1
GAME_STATE_SELECT_CHARACTER = 2
GAME_STATE_IN_GAME = 3
GAME_STATE_AFTER_IN_GAME = 4
DEFAULT_EMU_PACKAGE_NAME = "com.chinesegamer.wlnmy"


class DisconnectHandler:
    """斷線偵測與自動重連處理器。"""

    def __init__(self, bot=None):
        self.bot = bot
        self.is_disconnected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

        self.enabled = True
        self.same_screen_timeout = 45.0
        self.screen_hash_interval = 1.0
        self.screen_hash_diff_threshold = 5.0
        self.action_cooldown = 1.0
        self.auto_feature_scan_interval = 0.6
        self.auto_feature_action_cooldown = 1.0
        self.login_timeout = 120.0
        self.post_login_timeout = 45.0
        self.in_game_confirm_timeout = 25.0
        self.pc_launch_wait_timeout = 25.0
        self.emu_close_settle_seconds = 3.0
        self.emu_close_timeout_seconds = 15.0
        self.emu_launch_warmup_seconds = 6.0
        self.restart_game_enabled = True
        self.login_game_enabled = True
        self.auto_enable_features_enabled = True
        self.auto_enable_wander = True
        self.auto_enable_ai = True
        self.server_click_point = [RECONNECT_SERVER_CLICK_POINT[0], RECONNECT_SERVER_CLICK_POINT[1]]
        self.pc_exe_path = ""
        self.emu_package_name = ""
        self.detected_emu_package_name = ""

        self.last_signature = None
        self.last_hash_check_time = 0.0
        self.last_motion_time = 0.0

        self.recovery_active = False
        self.recovery_reason = ""
        self.current_flow = None
        self.current_step = None
        self.flow_start_time = 0.0
        self.last_action_time = 0.0
        self.pending_segment_test = ""
        self.no_screen_fail_count = 0
        self.no_screen_fail_threshold = 3
        self.no_screen_last_time = 0.0
        self.pc_launch_guard_until = 0.0
        self.pc_window_lost_retry_cooldown_until = 0.0
        self.pc_launched_pid = 0
        self.pc_hwnd_snapshot_before_launch = set()
        self.pc_prelaunch_exe_pids = set()
        self.pc_expected_new_pids = set()
        self.game_state = GAME_STATE_DISCONNECT
        self._log_throttle_state = {}
        self._frame_template_cache = {}
        self._emu_close_attempts = 0
        self._emu_close_started_at = 0.0
        self._emu_not_foreground_since = 0.0
        self._ai_clicked_on_state3_exit = False
        self._state3_dont_ask_clicked = False
        self._state3_wait_started_at = 0.0
        self._last_auto_feature_check_time = 0.0
        self._state4_not_in_battle_frames = 0
        self._state4_ai_off_seen_frames = 0
        self._state4_ai_last_click_at = 0.0
        self._flow_c_ai_off_seen_frames = 0
        self._flow_c_ai_last_click_at = 0.0
        self.check_game_open_interval_pc = 60.0
        self.check_game_open_interval_emu = 60.0
        self._last_game_open_check_pc = time.time()
        self._last_game_open_check_emu = time.time()
        self.scheduled_restart_enabled = False
        self.scheduled_restart_hours = 0
        self.scheduled_restart_minutes = 0
        self._last_scheduled_restart_ts = time.time()

        self._refresh_config()

    def _refresh_config(self):
        cfg = _config.RUNNING_CONFIG.get("disconnect", {}) if _config.RUNNING_CONFIG else {}
        self.enabled = bool(cfg.get("enabled", True))
        self.same_screen_timeout = float(cfg.get("same_screen_timeout", 45.0))
        self.screen_hash_interval = float(cfg.get("screen_hash_interval", 1.0))
        self.screen_hash_diff_threshold = float(cfg.get("screen_hash_diff_threshold", 5.0))
        self.max_reconnect_attempts = int(cfg.get("max_reconnect_attempts", 5))
        self.action_cooldown = float(cfg.get("action_cooldown", 1.0))
        self.auto_feature_scan_interval = float(cfg.get("auto_feature_scan_interval", 0.6))
        self.auto_feature_action_cooldown = float(cfg.get("auto_feature_action_cooldown", self.action_cooldown))
        self.login_timeout = float(cfg.get("login_timeout", 120.0))
        self.post_login_timeout = float(cfg.get("post_login_timeout", 45.0))
        self.in_game_confirm_timeout = float(cfg.get("in_game_confirm_timeout", 25.0))
        self.pc_launch_wait_timeout = float(cfg.get("pc_launch_wait_timeout", 25.0))
        self.emu_close_settle_seconds = float(cfg.get("emu_close_settle_seconds", 3.0))
        self.emu_close_timeout_seconds = float(cfg.get("emu_close_timeout_seconds", 15.0))
        self.emu_launch_warmup_seconds = float(cfg.get("emu_launch_warmup_seconds", 6.0))
        self.restart_game_enabled = bool(cfg.get("restart_game_enabled", True))
        self.login_game_enabled = bool(cfg.get("login_game_enabled", True))
        self.auto_enable_features_enabled = bool(cfg.get("auto_enable_features_enabled", True))
        self.auto_enable_wander = bool(cfg.get("auto_enable_wander", True))
        self.auto_enable_ai = bool(cfg.get("auto_enable_ai", True))
        self.check_game_open_interval_pc = float(cfg.get("check_game_open_interval_pc", 60.0))
        self.check_game_open_interval_emu = float(cfg.get("check_game_open_interval_emu", 60.0))
        self.scheduled_restart_enabled = bool(cfg.get("scheduled_restart_enabled", False))
        self.scheduled_restart_hours = int(cfg.get("scheduled_restart_hours", 0))
        self.scheduled_restart_minutes = int(cfg.get("scheduled_restart_minutes", 0))
        self.scheduled_restart_hours = max(0, min(23, self.scheduled_restart_hours))
        self.scheduled_restart_minutes = max(0, min(59, self.scheduled_restart_minutes))
        # 每台設備個別設定覆寫全域設定
        daf = getattr(self.bot, "device_auto_features", None)
        if daf is not None:
            self.auto_enable_wander = bool(daf.get("wander", self.auto_enable_wander))
            self.auto_enable_ai = bool(daf.get("ai", self.auto_enable_ai))
        feature_overrides = getattr(self.bot, "device_feature_overrides", None)
        if feature_overrides:
            self.enabled = bool(feature_overrides.get("disconnect_enabled", self.enabled))
            self.auto_enable_features_enabled = bool(
                feature_overrides.get("auto_enable_features_enabled", self.auto_enable_features_enabled)
            )
            self.scheduled_restart_enabled = bool(
                feature_overrides.get("scheduled_restart_enabled", self.scheduled_restart_enabled)
            )
        # 選服座標固定為常數設定，不接受設定檔覆蓋。
        self.server_click_point = [RECONNECT_SERVER_CLICK_POINT[0], RECONNECT_SERVER_CLICK_POINT[1]]
        self.pc_exe_path = str(cfg.get("pc_exe_path", "") or "")
        # 設定檔空白時使用內建預設套件，避免關閉後重新偵測抓錯。
        self.emu_package_name = str(cfg.get("emu_package_name", "") or DEFAULT_EMU_PACKAGE_NAME)

    def refresh_config(self):
        """對外公開的設定刷新入口。"""
        self._refresh_config()

    def check(self, screen):
        """
        檢查當前畫面是否為斷線狀態。

        Returns:
            True  - 正在處理斷線，主循環應跳過本幀
            False - 連線正常，繼續正常流程
        """
        if self.bot is None:
            return False

        if not self.bot.running:
            return False

        if screen is None or not isinstance(screen, np.ndarray):
            # EMU 在關閉/重啟期間可能短暫截圖失敗；若正在 recovery，仍需繼續流程推進。
            if self.recovery_active:
                self._refresh_config()
                self._frame_template_cache = {}
                return self._run_recovery(None)

            # 即使無畫面，也要允許定時檢查在所有狀態觸發，
            # 避免「遊戲已關閉 -> 無法截圖」時完全不會進入重開流程。
            self._refresh_config()
            if self.enabled and self._run_periodic_game_open_check(None):
                return True
            return False

        self._refresh_config()
        self._frame_template_cache = {}

        if _state.DEBUG_MODE:
            state_names = {
                GAME_STATE_DISCONNECT: "DISCONNECT",
                GAME_STATE_SELECT_CHARACTER: "SELECT_CHARACTER",
                GAME_STATE_IN_GAME: "IN_GAME",
                GAME_STATE_AFTER_IN_GAME: "AFTER_IN_GAME",
            }
            self._log_throttled(
                "check_state",
                f"[DISCONNECT][DEBUG] game_state={state_names.get(self.game_state, self.game_state)}"
                f" | enabled={self.enabled} | recovery={self.recovery_active}",
                interval_sec=5.0,
            )

        if not self.enabled:
            if not self.auto_enable_features_enabled:
                self._reset_screen_tracking(screen)
                return False

            # 斷線重連關閉時，仍需同步遊戲 state，
            # 讓僅開啟自動開啟功能時可進入 STATE-4 做功能維護。
            self._sync_game_state_from_screen(screen)
            if self.game_state == GAME_STATE_AFTER_IN_GAME:
                return self._check_state_after_in_game(screen)

            self._reset_screen_tracking(screen)
            return False

        pending_segment = self._consume_segment_test()
        if pending_segment:
            return self._run_segment_test(screen, pending_segment)

        if self.recovery_active:
            return self._run_recovery(screen)

        # 全狀態定時檢查：不限制必須先進入遊戲。
        if self._run_scheduled_restart_check(screen):
            return True
        if self._run_periodic_game_open_check(screen):
            return True

        # 遊戲狀態機
        if self.game_state == GAME_STATE_DISCONNECT:
            return self._check_state_disconnect(screen)
        if self.game_state == GAME_STATE_SELECT_CHARACTER:
            return self._check_state_select_character(screen)
        if self.game_state == GAME_STATE_IN_GAME:
            return self._check_state_in_game(screen)
        if self.game_state == GAME_STATE_AFTER_IN_GAME:
            return self._check_state_after_in_game(screen)
        return False

    def handle_missing_screen(self):
        """
        處理「截圖失敗/視窗消失」情境。

        主要用於 PC 模式：若視窗已不存在，連續多次失敗後直接進流程 A 重開遊戲。
        """
        if self.bot is None:
            return False

        self._refresh_config()
        if not self.enabled:
            self.no_screen_fail_count = 0
            return False

        if str(getattr(self.bot, "mode", "")) != "1":
            return False

        now = time.time()

        if self._try_attach_launched_pc_window():
            self.no_screen_fail_count = 0
            return False

        # 啟動後給遊戲一段建立視窗的時間，避免重複觸發重開。
        if now < self.pc_launch_guard_until:
            return False

        # 若視窗仍有效，將失敗計數歸零，不啟動重連。
        if self._is_pc_window_valid():
            self.no_screen_fail_count = 0
            return False

        # 相隔過久視為新的失敗序列，避免歷史計數誤觸發。
        if now - self.no_screen_last_time > 2.0:
            self.no_screen_fail_count = 0
        self.no_screen_last_time = now

        self.no_screen_fail_count += 1

        if self.recovery_active:
            return self._run_recovery(None)

        if self.no_screen_fail_count < self.no_screen_fail_threshold:
            return False

        if now < self.pc_window_lost_retry_cooldown_until:
            return False

        if not self.restart_game_enabled:
            self.bot.log("[DISCONNECT] 偵測到 PC 遊戲視窗已消失，但流程 A 已停用，無法自動重開。")
            return False

        self.bot.log("[DISCONNECT] 偵測到 PC 遊戲視窗已消失，進入流程 A 直接重啟遊戲。")
        self.pc_window_lost_retry_cooldown_until = now + 8.0
        self._enter_recovery("pc_window_lost")
        self._transition("A", "launch_game")
        return self._run_recovery(None)

    def _sync_game_state_from_screen(self, screen):
        """根據當前畫面被動同步 game_state（不主動啟動重連流程）。"""
        if self._is_in_game_screen(screen):
            self.game_state = GAME_STATE_AFTER_IN_GAME
            return

        if self._has_template(screen, "select_character"):
            self.game_state = GAME_STATE_SELECT_CHARACTER
            return

        if (
            self._has_template(screen, "custom_login")
            or self._has_template(screen, "multi_login")
            or self._has_template(screen, "select_server")
            or self._has_template(screen, "disconnect_hint")
        ):
            self.game_state = GAME_STATE_DISCONNECT
            return

    def _check_state_disconnect(self, screen):
        """game_state=1: 登入畫面偵測，處理公告、斷線彈窗與登入流程。"""
        # 快速前進：若已在遊戲內，直接進入 after_in_game。
        if self._is_in_game_screen(screen):
            self.game_state = GAME_STATE_AFTER_IN_GAME
            self._reset_screen_tracking(screen)
            self.bot.log("[STATE-1] 偵測到遊戲中畫面，直接進入 after_in_game 狀態。")
            return True

        if self._handle_start_game_announcement(screen, "STATE-1"):
            return True

        # 異地登入偵測 → 停止腳本，不進入重連流程
        if self._has_template(screen, "login_from_other_place"):
            self.bot.log("[STATE-1] 偵測到異地登入提示，停止腳本。")
            self._click_template(screen, "btn_confirm")
            self.bot.stop()
            self.recovery_active = False
            return False

        if self._click_template(screen, "update_resource"):
            self.bot.log("[STATE-1] 偵測到遊戲更新資源彈窗，已點擊 btn_confirm。")
            return True

        # 斷線彈窗偵測（btn_reconnect 優先於 btn_confirm / btn_back_to_login）
        if self._click_template(screen, "btn_reconnect"):
            self._handle_pop_gift_after_reconnect(screen, "STATE-1")
            if self.auto_enable_features_enabled:
                self.bot.log("[STATE-1] 偵測到重新連線按鈕並點擊，進入流程 C。")
                self.recovery_active = True
                self.is_disconnected = True
                self.recovery_reason = "btn_reconnect"
                self._transition("C", "wait_in_game")
                return True
            self.bot.log("[STATE-1] 偵測到重新連線按鈕並點擊，略過自動開啟功能。")
            return False

        # 通用確認彈窗偵測（btn_reconnect 之後）
        if self._click_template(screen, "btn_confirm"):
            self.bot.log("[STATE-1] 偵測到確認彈窗，已點擊 btn_confirm。")
            return True

        if self._click_template(screen, "btn_back_to_login"):
            self.bot.log("[STATE-1] 偵測到返回登入按鈕並點擊。")
            return True

        if self._has_template(screen, "disconnect_hint"):
            return True

        # 偵測到角色選擇 → 狀態 2
        if self._has_template(screen, "select_character"):
            self.game_state = GAME_STATE_SELECT_CHARACTER
            self.bot.log("[STATE-1] 偵測到 select_character，進入角色選擇狀態。")
            return True

        # 登入流程（需勾選登入遊戲）
        if self.login_game_enabled:
            if self._has_template(screen, "custom_login"):
                if not self._click_template(screen, "btn_login_account"):
                    self._click_template(screen, "btn_confirm")
                return True

            if self._has_template(screen, "multi_login"):
                self._handle_multi_login(screen, "STATE-1")
                return True

            if self._has_template(screen, "select_server"):
                if self._click_point(self.server_click_point[0], self.server_click_point[1]):
                    self.bot.log("[STATE-1] 已點擊選服。")
                return True

        return False

    def _check_state_select_character(self, screen):
        """game_state=2: 角色選擇畫面，偵測 select_character 與 login_game_button。"""
        # 快速前進
        if self._is_in_game_screen(screen):
            self.game_state = GAME_STATE_AFTER_IN_GAME
            self._reset_screen_tracking(screen)
            self.bot.log("[STATE-2] 偵測到遊戲中畫面，直接進入 after_in_game 狀態。")
            return True

        if self._handle_start_game_announcement(screen, "STATE-2"):
            return True

        if self._has_template(screen, "select_character"):
            self._click_template(screen, "login_game_button")
            return True

        # select_character 消失 → 進入 in_game 狀態
        self.game_state = GAME_STATE_IN_GAME
        self._ai_clicked_on_state3_exit = False
        self._state3_dont_ask_clicked = False
        self._state3_wait_started_at = time.time()
        self.bot.log("[STATE-2] 角色選擇畫面已消失，進入 in_game 狀態。")
        return True

    def _check_state_in_game(self, screen):
        """game_state=3: 進入遊戲中，處理登入後彈窗與偵測 btn_power_saving。"""
        if self._state3_wait_started_at <= 0.0:
            self._state3_wait_started_at = time.time()

        # 先處理公告/彈窗，避免 EMU 動作慢來不及關閉就跳到下一狀態
        if self._handle_start_game_announcement(screen, "STATE-3"):
            return True

        # 登入後彈窗處理（含一般公告 dont_ask_today + btn_cross）
        handled, self.last_action_time = handle_post_login_popups(
            self.bot,
            screen,
            "STATE-3",
            self.last_action_time,
            self.action_cooldown,
            self.bot.log,
        )
        if handled:
            return True

        # 偵測到遊戲中畫面 → 狀態 4
        if self._is_in_game_screen(screen):
            self._try_click_ai_on_state3_exit(screen)
            self.game_state = GAME_STATE_AFTER_IN_GAME
            self._state3_wait_started_at = 0.0
            self._state3_dont_ask_clicked = False
            self._reset_screen_tracking(screen)
            self.bot.log("[STATE-3] 偵測到遊戲中畫面，進入 after_in_game 狀態。")
            return True

        elapsed = time.time() - self._state3_wait_started_at
        if elapsed < self.in_game_confirm_timeout:
            self._log_throttled(
                "state3_wait_in_game",
                (
                    "[STATE-3] 等待遊戲中畫面中"
                    f"（{elapsed:.1f}/{self.in_game_confirm_timeout:.1f}s）。"
                ),
                1.0,
            )
            return True

        # 逾時後才轉移，避免載入較慢時過早跳過偵測。
        self._try_click_ai_on_state3_exit(screen)
        self.game_state = GAME_STATE_AFTER_IN_GAME
        self._state3_wait_started_at = 0.0
        self._state3_dont_ask_clicked = False
        self._reset_screen_tracking(screen)
        self.bot.log("[STATE-3] 等待遊戲中畫面逾時，切換至 after_in_game 狀態。")
        return True

    def _check_state_after_in_game(self, screen):
        """game_state=4: 遊戲中監控斷線與自動功能維護。"""
        if self._handle_start_game_announcement(screen, "STATE-4"):
            return True

        # 一般公告彈窗（含 dont_ask_today + btn_cross）
        if self._has_template(screen, "announcement"):
            if self._has_template(screen, "dont_ask_today"):
                if self._click_template(screen, "dont_ask_today"):
                    self.bot.log("[STATE-4] 偵測到公告彈窗，已先點擊 dont_ask_today。")
                else:
                    self._log_throttled(
                        "state4_announcement_wait_dontask",
                        "[STATE-4] 偵測到公告彈窗且有 dont_ask_today，等待可點擊後再關閉。",
                        1.0,
                    )
                return True

            if getattr(self.bot, "mode", "") == "2":
                if self._can_act():
                    self.bot.execute_key("esc", android_keycode=111)
                    self.last_action_time = time.time()
                    self.bot.log("[STATE-4] 偵測到公告彈窗，已送出 ESC 關閉。")
            else:
                if self._click_template(screen, "btn_cross"):
                    self.bot.log("[STATE-4] 偵測到公告彈窗，已點擊 btn_cross 關閉。")
            return True

        # 斷線偵測
        reason = self._detect_disconnect(screen) if self.enabled else ""
        if reason:
            # 異地登入 → 點確認後停止，不進入重連
            if reason == "login_from_other_place":
                self.bot.log("[STATE-4] 偵測到異地登入，停止腳本。")
                self._click_template(screen, "btn_confirm")
                self.bot.stop()
                self.recovery_active = False
                return False

            self.game_state = GAME_STATE_DISCONNECT
            self._enter_recovery(reason)
            return self._run_recovery(screen)

        # 反向偵測：若非遊戲中畫面，檢查是否回到登入/選角
        in_battle = self._has_template(screen, "in_battle")
        _prev_not_battle = self._state4_not_in_battle_frames
        if in_battle:
            self._state4_not_in_battle_frames = 0
            if _prev_not_battle >= 5:
                # 脫離戰鬥超過5幀後重新偵測到戰鬥，清空 AI 偵測防抖狀態。
                self._state4_ai_off_seen_frames = 0
        else:
            self._state4_not_in_battle_frames += 1

        if not self._is_in_game_screen(screen):
            if self._has_template(screen, "select_character"):
                self.game_state = GAME_STATE_SELECT_CHARACTER
                self._reset_screen_tracking(screen)
                self.bot.log("[STATE-4] 偵測到角色選擇畫面，轉回 select_character 狀態。")
                return True
            if (self._has_template(screen, "custom_login")
                    or self._has_template(screen, "multi_login")
                    or self._has_template(screen, "select_server")):
                self.game_state = GAME_STATE_DISCONNECT
                self._reset_screen_tracking(screen)
                self.bot.log("[STATE-4] 偵測到登入畫面，轉回 disconnect 狀態。")
                return True

        # Debug 模式下，戰鬥中固定探針一次 AI 關閉按鈕，確保可看到 SEARCH 分數。
        if _state.DEBUG_MODE and in_battle:
            self._has_template(screen, "btn_ai_off_in_battle")

        # 自動功能維護
        if not self.auto_enable_features_enabled:
            return False

        acted = False
        if not self._should_check_auto_feature_scan():
            return False

        ai_off_in_battle = False
        if self.auto_enable_ai and in_battle:
            ai_off_in_battle = self._has_template(screen, "btn_ai_off_in_battle")
            if ai_off_in_battle:
                self._state4_ai_off_seen_frames += 1
            else:
                self._state4_ai_off_seen_frames = 0
        else:
            self._state4_ai_off_seen_frames = 0

        if self.auto_enable_ai and in_battle:
            if ai_off_in_battle:
                now = time.time()
                click_cooldown = max(self.auto_feature_action_cooldown * 2.0, 1.2)
                if self._state4_ai_off_seen_frames < 2:
                    self._log_throttled(
                        "state4_ai_wait_stable_in_battle",
                        "[STATE-4] 戰鬥中偵測到 AI 關閉，等待連續命中確認後再點擊。",
                        2.0,
                    )
                elif (now - self._state4_ai_last_click_at) < click_cooldown:
                    self._log_throttled(
                        "state4_ai_click_cooldown",
                        "[STATE-4] 戰鬥中 AI 重試冷卻中，持續監看。",
                        2.0,
                    )
                elif self._click_template(screen, "btn_ai_off_in_battle", cooldown=self.auto_feature_action_cooldown):
                    self._state4_ai_last_click_at = time.time()
                    self.bot.log("[STATE-4] 戰鬥中 AI 關閉，已嘗試開啟（持續監看模式）。")
                    acted = True
            else:
                if _state.DEBUG_MODE:
                    self._log_throttled(
                        "state4_ai_already_on_in_battle",
                        "[STATE-4] 戰鬥中未偵測到 AI 關閉按鈕，持續監看中。",
                        3.0,
                    )
        if self.auto_enable_wander:
            if not in_battle:
                if not self._has_template(screen, "btn_wander_on"):
                    if self._click_template(screen, "btn_wander_off", cooldown=self.auto_feature_action_cooldown):
                        self.bot.log("[STATE-4] 一般地圖徘徊關閉，已嘗試開啟。")
                        acted = True

        return acted

    def request_segment_test(self, segment):
        """由 GUI 觸發分段測試。"""
        seg = str(segment or "").strip().upper()
        if seg in {"A", "B", "C", "ALL"}:
            self.pending_segment_test = seg

    def _consume_segment_test(self):
        segment = self.pending_segment_test
        self.pending_segment_test = ""
        return segment

    def _run_segment_test(self, screen, segment):
        """執行 GUI 分段測試請求。"""
        if segment == "A":
            if not self.restart_game_enabled:
                self.bot.log("[TEST-A][WARN] 流程 A 已停用，無法執行測試。")
                return False
            self.bot.log("[TEST-A] 已觸發流程 A 測試。")
            self.recovery_active = True
            self.is_disconnected = True
            self.recovery_reason = "manual_test_a"
            self._transition("A", "close_game")
            return self._run_recovery(screen)

        if segment == "B":
            if not self.login_game_enabled:
                self.bot.log("[TEST-B][WARN] 流程 B 已停用，無法執行測試。")
                return False
            self.bot.log("[TEST-B] 已觸發流程 B 測試。")
            self.recovery_active = True
            self.is_disconnected = True
            self.recovery_reason = "manual_test_b"
            self._transition("B", "wait_login_scene")
            return self._run_recovery(screen)

        if segment == "C":
            if not self.auto_enable_features_enabled:
                self.bot.log("[TEST-C][WARN] 流程 C 已停用，無法執行測試。")
                return False
            self.bot.log("[TEST-C] 已觸發流程 C 測試。")
            self.recovery_active = True
            self.is_disconnected = True
            self.recovery_reason = "manual_test_c"
            self._transition("C", "enable_lurk")
            return self._run_recovery(screen)

        self.bot.log("[TEST-ALL] 已觸發完整流程測試。")
        self.recovery_active = True
        self.is_disconnected = True
        self.recovery_reason = "manual_test_all"
        self._transition("ENTRY", "decide")
        return self._run_recovery(screen)

    def _handle_multi_login(self, screen, flow_tag):
        """multi_login 畫面優先點 custom_login，失敗時回退點 multi_login。"""
        if self._click_template(screen, "custom_login"):
            self.bot.log(f"[{flow_tag}] 已點擊 custom_login。")
            return True

        if self._click_template(screen, "multi_login"):
            self.bot.log(f"[{flow_tag}] custom_login 未命中，已回退點擊 multi_login。")
            return True

        return False

    def _detect_disconnect(self, screen):
        """在 after_in_game 狀態下偵測斷線原因。"""
        if self._has_template(screen, "login_from_other_place"):
            return "login_from_other_place"
        if self._has_template(screen, "disconnect_hint"):
            return "disconnect_hint"
        if self._has_template(screen, "btn_reconnect"):
            return "btn_reconnect"
        if self._has_template(screen, "btn_back_to_login"):
            return "btn_back_to_login"
        if self._is_screen_stuck(screen):
            return "same_screen_stuck"
        return ""

    def _is_in_game_screen(self, screen):
        """判斷當前畫面是否可視為已進入遊戲（避免啟動前誤判）。"""
        # 主指標：命中即視為在遊戲中。
        if self._has_template(screen, "btn_power_saving") or self._has_template(screen, "in_battle"):
            return True

        # 前置/登入畫面命中時，不接受次指標判斷，避免誤判為 after_in_game。
        if (
            self._has_template(screen, "custom_login")
            or self._has_template(screen, "multi_login")
            or self._has_template(screen, "select_server")
            or self._has_template(screen, "select_character")
            or self._has_template(screen, "start_game_announcement")
        ):
            return False

        # 次指標：至少 2 個命中才判定在遊戲中，降低啟動前誤判。
        secondary_hits = 0
        for key in (
            "btn_wander_on",
            "btn_wander_off",
            "btn_ai",
            "btn_ai_off_in_battle",
        ):
            if self._has_template(screen, key):
                secondary_hits += 1
                if secondary_hits >= 2:
                    return True
        return False

    def _try_click_ai_on_state3_exit(self, screen):
        """當 state 從 in_game(3) 轉到 after_in_game(4) 時，AI 只嘗試點一次。"""
        if self._ai_clicked_on_state3_exit:
            return False
        if not self.auto_enable_features_enabled or not self.auto_enable_ai:
            self._ai_clicked_on_state3_exit = True
            return False
        if screen is None:
            self._ai_clicked_on_state3_exit = True
            return False
        if self._click_template(screen, "btn_ai", cooldown=self.auto_feature_action_cooldown):
            self.bot.log("[STATE-3] in_game -> after_in_game：已點擊 AI 按鈕一次。")
            self._ai_clicked_on_state3_exit = True
            return True
        self.bot.log("[STATE-3] in_game -> after_in_game：未偵測到 AI 按鈕，略過一次性點擊。")
        self._ai_clicked_on_state3_exit = True
        return False

    def _screen_signature(self, screen):
        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
        return small.astype(np.float32)

    def _reset_screen_tracking(self, screen=None):
        now = time.time()
        if screen is not None and isinstance(screen, np.ndarray):
            self.last_signature = self._screen_signature(screen)
        else:
            self.last_signature = None
        self.last_hash_check_time = now
        self.last_motion_time = now

    def _is_screen_stuck(self, screen):
        # 只在進入遊戲後才檢測同畫面停滯斷線。
        # 若未進入遊戲，直接重置追蹤，避免在加載/登入等待階段誤判。
        if not self._is_in_game_screen(screen):
            if _state.DEBUG_MODE:
                self._log_throttled(
                    "same_screen_skip_not_ingame",
                    "[DISCONNECT][DEBUG] 同畫面偵測略過：未偵測到遊戲中畫面。",
                    interval_sec=3.0,
                )
            self._reset_screen_tracking(screen)
            return False

        now = time.time()
        if self.last_signature is None:
            if _state.DEBUG_MODE:
                self._log_throttled(
                    "same_screen_init_signature",
                    "[DISCONNECT][DEBUG] 同畫面偵測初始化：建立首幀簽名。",
                    interval_sec=3.0,
                )
            self._reset_screen_tracking(screen)
            return False

        if now - self.last_hash_check_time < self.screen_hash_interval:
            if _state.DEBUG_MODE:
                self._log_throttled(
                    "same_screen_wait_interval",
                    "[DISCONNECT][DEBUG] 同畫面偵測等待中：尚未到達偵測間隔。",
                    interval_sec=3.0,
                )
            return False

        current_sig = self._screen_signature(screen)
        self.last_hash_check_time = now

        diff = float(np.mean(np.abs(current_sig - self.last_signature)))

        if _state.DEBUG_MODE:
            stuck_elapsed = now - self.last_motion_time
            self.bot.log(
                f"[DISCONNECT][DEBUG] 分數:{diff:.2f}| 閾值:{self.screen_hash_diff_threshold:g}"
                f"|經過時間:{stuck_elapsed:g}s|逾時時間:{self.same_screen_timeout:g}s"
            )

        if diff > self.screen_hash_diff_threshold:
            self.last_signature = current_sig
            self.last_motion_time = now
            return False

        if now - self.last_motion_time >= self.same_screen_timeout:
            stuck_elapsed = now - self.last_motion_time
            self.bot.log(
                f"[DISCONNECT] 同畫面逾時 分數:{diff:.2f}| 閾值:{self.screen_hash_diff_threshold:g}"
                f"|經過時間:{stuck_elapsed:g}s|逾時時間:{self.same_screen_timeout:g}s"
            )
            return True
        return False

    def _is_pc_window_valid(self):
        """檢查 PC 視窗 hwnd 是否仍存在。"""
        if self.bot is None:
            return False

        try:
            hwnd = int(getattr(self.bot, "hwnd", 0) or 0)
        except Exception:
            return False

        if hwnd <= 0:
            return False

        try:
            return bool(ctypes.windll.user32.IsWindow(hwnd))
        except Exception:
            return False

    def _try_attach_launched_pc_window(self):
        if self.bot is None or str(getattr(self.bot, "mode", "")) != "1":
            return False
        if self._is_pc_window_valid():
            self.pc_launched_pid = 0
            self.pc_hwnd_snapshot_before_launch = set()
            self.pc_prelaunch_exe_pids = set()
            self.pc_expected_new_pids = set()
            return True
        if (
            self.pc_launched_pid <= 0
            and not self.pc_hwnd_snapshot_before_launch
            and not self.pc_prelaunch_exe_pids
            and not self.pc_expected_new_pids
        ):
            return False
        if win32gui is None:
            return False

        hwnd = 0
        if self.pc_launched_pid > 0 and win32process is not None:
            pass

    def request_segment_test(self, segment):
        """由 GUI 觸發分段測試。"""
        seg = str(segment or "").strip().upper()
        if seg in {"A", "B", "C", "ALL"}:
            self.pending_segment_test = seg

    def _consume_segment_test(self):
        segment = self.pending_segment_test
        self.pending_segment_test = ""
        return segment

    def _run_segment_test(self, screen, segment):
        """執行 GUI 分段測試請求。"""
        if segment == "A":
            if not self.restart_game_enabled:
                self.bot.log("[TEST-A][WARN] 流程 A 已停用，無法執行測試。")
                return False
            self.bot.log("[TEST-A] 已觸發流程 A 測試。")
            self.recovery_active = True
            self.is_disconnected = True
            self.recovery_reason = "manual_test_a"
            self._transition("A", "close_game")
            return self._run_recovery(screen)

        if segment == "B":
            if not self.login_game_enabled:
                self.bot.log("[TEST-B][WARN] 流程 B 已停用，無法執行測試。")
                return False
            self.bot.log("[TEST-B] 已觸發流程 B 測試。")
            self.recovery_active = True
            self.is_disconnected = True
            self.recovery_reason = "manual_test_b"
            self._transition("B", "wait_login_scene")
            return self._run_recovery(screen)

        if segment == "C":
            if not self.auto_enable_features_enabled:
                self.bot.log("[TEST-C][WARN] 流程 C 已停用，無法執行測試。")
                return False
            self.bot.log("[TEST-C] 已觸發流程 C 測試。")
            self.recovery_active = True
            self.is_disconnected = True
            self.recovery_reason = "manual_test_c"
            self._transition("C", "enable_lurk")
            return self._run_recovery(screen)

        self.bot.log("[TEST-ALL] 已觸發完整流程測試。")
        self.recovery_active = True
        self.is_disconnected = True
        self.recovery_reason = "manual_test_all"
        self._transition("ENTRY", "decide")
        return self._run_recovery(screen)

    def _handle_multi_login(self, screen, flow_tag):
        """multi_login 畫面優先點 custom_login，失敗時回退點 multi_login。"""
        if self._click_template(screen, "custom_login"):
            self.bot.log(f"[{flow_tag}] 已點擊 custom_login。")
            return True

        if self._click_template(screen, "multi_login"):
            self.bot.log(f"[{flow_tag}] custom_login 未命中，已回退點擊 multi_login。")
            return True

        return True

    def _detect_disconnect(self, screen):
        """在 after_in_game 狀態下偵測斷線原因。"""
        if self._has_template(screen, "login_from_other_place"):
            return "login_from_other_place"
        if self._has_template(screen, "disconnect_hint"):
            return "disconnect_hint"
        if self._has_template(screen, "btn_reconnect"):
            return "btn_reconnect"
        if self._has_template(screen, "btn_back_to_login"):
            return "btn_back_to_login"
        if self._is_screen_stuck(screen):
            return "same_screen_stuck"
        return ""

    def _is_in_game_screen(self, screen):
        """判斷當前畫面是否可視為已進入遊戲（避免啟動前誤判）。"""
        # 主指標：命中即視為在遊戲中。
        if self._has_template(screen, "btn_power_saving") or self._has_template(screen, "in_battle"):
            return True

        # 前置/登入畫面命中時，不接受次指標判斷，避免誤判為 after_in_game。
        if (
            self._has_template(screen, "custom_login")
            or self._has_template(screen, "multi_login")
            or self._has_template(screen, "select_server")
            or self._has_template(screen, "select_character")
            or self._has_template(screen, "start_game_announcement")
        ):
            return False

        # 次指標：至少 2 個命中才判定在遊戲中，降低啟動前誤判。
        secondary_hits = 0
        for key in (
            "btn_wander_on",
            "btn_wander_off",
            "btn_ai",
            "btn_ai_off_in_battle",
        ):
            if self._has_template(screen, key):
                secondary_hits += 1
                if secondary_hits >= 2:
                    return True
        return False

    def _try_click_ai_on_state3_exit(self, screen):
        """當 state 從 in_game(3) 轉到 after_in_game(4) 時，AI 只嘗試點一次。"""
        if self._ai_clicked_on_state3_exit:
            return False
        if not self.auto_enable_features_enabled or not self.auto_enable_ai:
            self._ai_clicked_on_state3_exit = True
            return False
        if screen is None:
            self._ai_clicked_on_state3_exit = True
            return False
        if self._click_template(screen, "btn_ai", cooldown=self.auto_feature_action_cooldown):
            self.bot.log("[STATE-3] in_game -> after_in_game：已點擊 AI 按鈕一次。")
            self._ai_clicked_on_state3_exit = True
            return True
        self.bot.log("[STATE-3] in_game -> after_in_game：未偵測到 AI 按鈕，略過一次性點擊。")
        self._ai_clicked_on_state3_exit = True
        return False

    def _screen_signature(self, screen):
        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
        return small.astype(np.float32)

    def _reset_screen_tracking(self, screen=None):
        now = time.time()
        if screen is not None and isinstance(screen, np.ndarray):
            self.last_signature = self._screen_signature(screen)
        else:
            self.last_signature = None
        self.last_hash_check_time = now
        self.last_motion_time = now

    def _is_screen_stuck(self, screen):
        # 只在進入遊戲後才檢測同畫面停滯斷線。
        # 若未進入遊戲，直接重置追蹤，避免在加載/登入等待階段誤判。
        if not self._is_in_game_screen(screen):
            if _state.DEBUG_MODE:
                self._log_throttled(
                    "same_screen_skip_not_ingame",
                    "[DISCONNECT][DEBUG] 同畫面偵測略過：未偵測到遊戲中畫面。",
                    interval_sec=3.0,
                )
            self._reset_screen_tracking(screen)
            return False

        now = time.time()
        if self.last_signature is None:
            if _state.DEBUG_MODE:
                self._log_throttled(
                    "same_screen_init_signature",
                    "[DISCONNECT][DEBUG] 同畫面偵測初始化：建立首幀簽名。",
                    interval_sec=3.0,
                )
            self._reset_screen_tracking(screen)
            return False

        if now - self.last_hash_check_time < self.screen_hash_interval:
            if _state.DEBUG_MODE:
                self._log_throttled(
                    "same_screen_wait_interval",
                    "[DISCONNECT][DEBUG] 同畫面偵測等待中：尚未到達偵測間隔。",
                    interval_sec=3.0,
                )
            return False

        current_sig = self._screen_signature(screen)
        self.last_hash_check_time = now

        diff = float(np.mean(np.abs(current_sig - self.last_signature)))

        if _state.DEBUG_MODE:
            stuck_elapsed = now - self.last_motion_time
            self.bot.log(
                f"[DISCONNECT][DEBUG] 分數:{diff:.2f}| 閾值:{self.screen_hash_diff_threshold:g}"
                f"|經過時間:{stuck_elapsed:g}s|逾時時間:{self.same_screen_timeout:g}s"
            )

        if diff > self.screen_hash_diff_threshold:
            self.last_signature = current_sig
            self.last_motion_time = now
            return False

        if now - self.last_motion_time >= self.same_screen_timeout:
            stuck_elapsed = now - self.last_motion_time
            self.bot.log(
                f"[DISCONNECT] 同畫面逾時 分數:{diff:.2f}| 閾值:{self.screen_hash_diff_threshold:g}"
                f"|經過時間:{stuck_elapsed:g}s|逾時時間:{self.same_screen_timeout:g}s"
            )
            return True
        return False

    def _is_pc_window_valid(self):
        """檢查 PC 視窗 hwnd 是否仍存在。"""
        if self.bot is None:
            return False

        try:
            hwnd = int(getattr(self.bot, "hwnd", 0) or 0)
        except Exception:
            return False

        if hwnd <= 0:
            return False

        try:
            return bool(ctypes.windll.user32.IsWindow(hwnd))
        except Exception:
            return False

    def _try_attach_launched_pc_window(self):
        if self.bot is None or str(getattr(self.bot, "mode", "")) != "1":
            return False
        if self._is_pc_window_valid():
            self.pc_launched_pid = 0
            self.pc_hwnd_snapshot_before_launch = set()
            self.pc_prelaunch_exe_pids = set()
            self.pc_expected_new_pids = set()
            return True
        if (
            self.pc_launched_pid <= 0
            and not self.pc_hwnd_snapshot_before_launch
            and not self.pc_prelaunch_exe_pids
            and not self.pc_expected_new_pids
        ):
            return False
        if win32gui is None:
            return False

        hwnd = 0
        if self.pc_launched_pid > 0 and win32process is not None:
            hwnd = self._find_visible_window_by_pid(self.pc_launched_pid)

        if hwnd <= 0:
            self._refresh_expected_new_pids()
            if self.pc_expected_new_pids:
                hwnd = self._find_visible_window_by_pid_set(self.pc_expected_new_pids)

        if hwnd <= 0:
            return False

        old_hwnd = int(getattr(self.bot, "hwnd", 0) or 0)
        self.bot.hwnd = hwnd
        self._refresh_bot_identity_with_hwnd(hwnd)
        self.pc_launched_pid = 0
        self.pc_hwnd_snapshot_before_launch = set()
        self.pc_prelaunch_exe_pids = set()
        self.pc_expected_new_pids = set()
        self.no_screen_fail_count = 0
        self.no_screen_last_time = 0.0
        self.bot.log(f"[FLOW-A] 已重新綁定新的 PC 遊戲視窗 hwnd={hwnd}。")
        # 通知 GUI 更新視窗資訊
        cb = getattr(self.bot, "on_hwnd_changed", None)
        if callable(cb):
            try:
                cb(old_hwnd, hwnd)
            except Exception:
                pass
        return True

    def _list_candidate_game_hwnds(self):
        if win32gui is None:
            return set()

        title_keyword = str(WINDOW_TITLE or "").strip()
        candidates = set()

        def enum_windows(hwnd, _):
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                title = str(win32gui.GetWindowText(hwnd) or "").strip()
                if not title:
                    return True
                if title_keyword and title_keyword not in title:
                    return True
                candidates.add(int(hwnd))
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(enum_windows, None)
        except Exception:
            return set()
        return candidates

    def _find_new_visible_game_window(self):
        current = self._list_candidate_game_hwnds()
        if not current:
            return 0

        new_hwnds = [h for h in current if h not in self.pc_hwnd_snapshot_before_launch]
        if new_hwnds:
            return max(new_hwnds)

        old_hwnd = int(getattr(self.bot, "hwnd", 0) or 0)
        if old_hwnd <= 0 or old_hwnd not in current:
            return max(current)
        return 0

    def _find_visible_window_by_pid(self, pid):
        if win32gui is None or win32process is None:
            return 0

        target_hwnd = 0

        def enum_windows(hwnd, _):
            nonlocal target_hwnd
            if target_hwnd:
                return False
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                if int(window_pid or 0) != int(pid):
                    return True
                title = str(win32gui.GetWindowText(hwnd) or "").strip()
                if not title:
                    return True
                target_hwnd = int(hwnd)
                return False
            except Exception:
                return True

        try:
            win32gui.EnumWindows(enum_windows, None)
        except Exception:
            return 0
        return target_hwnd

    def _find_visible_window_by_pid_set(self, pid_set):
        if win32gui is None or win32process is None:
            return 0

        pid_set = {int(p) for p in (pid_set or set()) if int(p) > 0}
        if not pid_set:
            return 0

        target_pid = min(pid_set)
        matched_hwnds = []

        def enum_windows(hwnd, _):
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                if int(window_pid or 0) != target_pid:
                    return True
                title = str(win32gui.GetWindowText(hwnd) or "").strip()
                if not title:
                    return True
                matched_hwnds.append(int(hwnd))
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(enum_windows, None)
        except Exception:
            return 0

        if not matched_hwnds:
            return 0
        return max(matched_hwnds)

    def _get_running_exe_pids(self):
        if not self.pc_exe_path:
            return set()

        exe_name = os.path.basename(self.pc_exe_path).strip()
        if not exe_name:
            return set()

        try:
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH", "/FI", f"IMAGENAME eq {exe_name}"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            output = (result.stdout or "").strip()
            if not output:
                return set()

            pids = set()
            rows = csv.reader(output.splitlines())
            for row in rows:
                if len(row) < 2:
                    continue
                raw_pid = str(row[1]).replace(",", "").strip()
                if raw_pid.isdigit():
                    pids.add(int(raw_pid))
            return pids
        except Exception:
            return set()

    def _refresh_expected_new_pids(self):
        if self.pc_expected_new_pids:
            return

        current = self._get_running_exe_pids()
        if not current:
            return

        expected = set()
        if self.pc_prelaunch_exe_pids:
            expected |= {pid for pid in current if pid not in self.pc_prelaunch_exe_pids}
        if self.pc_launched_pid > 0:
            expected.add(int(self.pc_launched_pid))

        if expected:
            self.pc_expected_new_pids = {int(pid) for pid in expected if int(pid) > 0}

    def _enter_recovery(self, reason):
        self.reconnect_attempts += 1
        self.is_disconnected = True
        self.recovery_active = True
        self.game_state = GAME_STATE_DISCONNECT
        self.recovery_reason = reason
        self.current_flow = "ENTRY"
        self.current_step = "inspect"
        self.flow_start_time = time.time()

        unlimited = (self.max_reconnect_attempts == 0)
        limit_str = "∞" if unlimited else str(self.max_reconnect_attempts)
        self.bot.log(
            f"[DISCONNECT] 觸發重連流程，原因={reason}，第 {self.reconnect_attempts}/{limit_str} 次。"
        )

        if not unlimited and self.reconnect_attempts > self.max_reconnect_attempts:
            self.bot.log("[DISCONNECT] 超過重連上限，停止腳本。")
            self.bot.stop()
            self.recovery_active = False

    def _run_recovery(self, screen):
        if not self.recovery_active:
            return False

        unlimited = (self.max_reconnect_attempts == 0)
        if not unlimited and self.reconnect_attempts > self.max_reconnect_attempts:
            return False

        if self.current_flow == "ENTRY":
            return self._run_entry_flow(screen)
        if self.current_flow == "A":
            return self._run_flow_a(screen)
        if self.current_flow == "B":
            return self._run_flow_b(screen)
        if self.current_flow == "C":
            return self._run_flow_c(screen)

        self._transition("A", "close_game")
        return True

    def _run_entry_flow(self, screen):
        if self._has_template(screen, "disconnect_hint"):
            self.bot.log("[DISCONNECT] 偵測到連線中斷提示畫面。")

        # 異地登入偵測 → 停止腳本，不進入重連流程
        if self._has_template(screen, "login_from_other_place"):
            self.bot.log("[DISCONNECT] 偵測到異地登入提示，停止腳本。")
            self._click_template(screen, "btn_confirm")
            self.bot.stop()
            self.recovery_active = False
            return False

        # btn_reconnect 優先於 btn_confirm / btn_back_to_login
        if self._click_template(screen, "btn_reconnect"):
            self._handle_pop_gift_after_reconnect(screen, "DISCONNECT")
            if self.auto_enable_features_enabled:
                self.bot.log("[DISCONNECT] 已按下重新連線，進入流程 C。")
                self._transition("C", "wait_in_game")
                return True
            self.bot.log("[DISCONNECT] 已按下重新連線，略過自動開啟功能，恢復主流程。")
            self._finish_recovery()
            return False

        # 通用確認彈窗偵測（btn_reconnect 之後）
        if self._click_template(screen, "btn_confirm"):
            self.bot.log("[DISCONNECT] 偵測到確認彈窗，已點擊 btn_confirm。")
            if self.recovery_reason == "disconnect_hint":
                if self.login_game_enabled:
                    self.bot.log("[DISCONNECT] 來源為 disconnect_hint，按下確認後改走流程 B（登入遊戲）。")
                    self._transition("B", "wait_login_scene")
                    return True
                if self.restart_game_enabled:
                    self.bot.log("[DISCONNECT] 來源為 disconnect_hint，但流程 B 停用，改走流程 A。")
                    self._transition("A", "close_game")
                    return True
                self.bot.log("[DISCONNECT] 重開/登入流程皆停用，停止腳本。")
                self.bot.stop()
                self.recovery_active = False
                return False
            if self.auto_enable_features_enabled:
                self.bot.log("[DISCONNECT] 已按下確認，進入流程 C 檢查進遊戲後狀態。")
                self._transition("C", "wait_in_game")
                return True
            self.bot.log("[DISCONNECT] 已按下確認，略過自動開啟功能，恢復主流程。")
            self._finish_recovery()
            return False

        clicked_dialog = False
        if self._click_template(screen, "btn_back_to_login"):
            clicked_dialog = True

        if clicked_dialog:
            if self.login_game_enabled:
                self.bot.log("[DISCONNECT] 已按下返回登入類按鈕，進入流程 B。")
                self._transition("B", "wait_login_scene")
            elif self.restart_game_enabled:
                self.bot.log("[DISCONNECT] 登入流程停用，改走流程 A。")
                self._transition("A", "close_game")
            else:
                self.bot.log("[DISCONNECT] 重開/登入流程皆停用，停止腳本。")
                self.bot.stop()
                self.recovery_active = False
            return True

        if self.recovery_reason == "same_screen_stuck":
            if self.restart_game_enabled:
                self.bot.log("[DISCONNECT] 卡畫面重連：改走流程 A 重開遊戲。")
                self._transition("A", "close_game")
            elif self.login_game_enabled:
                self.bot.log("[DISCONNECT] 重開流程停用，改走流程 B。")
                self._transition("B", "wait_login_scene")
            else:
                self.bot.log("[DISCONNECT] 重開/登入流程皆停用，停止腳本。")
                self.bot.stop()
                self.recovery_active = False
            return True

        if time.time() - self.flow_start_time > 5.0:
            if self.restart_game_enabled:
                self.bot.log("[DISCONNECT] 入口判斷逾時，改走流程 A。")
                self._transition("A", "close_game")
            elif self.login_game_enabled:
                self.bot.log("[DISCONNECT] 入口判斷逾時，改走流程 B。")
                self._transition("B", "wait_login_scene")
            else:
                self.bot.log("[DISCONNECT] 重開/登入流程皆停用，停止腳本。")
                self.bot.stop()
                self.recovery_active = False

        return True

    def _run_flow_a(self, screen):
        if not self.restart_game_enabled:
            if self.login_game_enabled:
                self.bot.log("[FLOW-A] 已停用，改走流程 B。")
                self._transition("B", "wait_login_scene")
                return True
            self.bot.log("[FLOW-A] 已停用且流程 B 也停用，停止腳本。")
            self.bot.stop()
            self.recovery_active = False
            return False

        if self.current_step == "close_game":
            self._close_game(screen)
            if self.bot.mode == "1":
                if time.time() - self.flow_start_time > 6.0:
                    self._transition("A", "launch_game")
            else:
                # EMU：使用「直接關閉測試」已驗證可行的 force-stop 路徑。
                package_name = self._resolve_emu_package_name()
                close_elapsed = max(0.0, time.time() - float(self._emu_close_started_at or self.flow_start_time))
                fg_state, current_pkg = self._get_emu_foreground_state(package_name)
                if fg_state == "not_foreground":
                    if close_elapsed >= 1.0:
                        self.bot.log("[FLOW-A] EMU 已離開遊戲，進入啟動流程。")
                        self._transition("A", "launch_game")
                        return True
                if close_elapsed >= max(3.0, self.emu_close_settle_seconds):
                    if fg_state == "unknown":
                        self.bot.log("[FLOW-A] EMU 前景狀態未知，直接關閉等待達門檻，進入啟動流程。")
                    elif fg_state == "foreground":
                        self.bot.log(
                            "[FLOW-A] EMU 前景仍為遊戲但直接關閉等待達門檻，進入啟動流程。"
                        )
                    else:
                        self.bot.log(
                            f"[FLOW-A] EMU 關閉等待達門檻（當前前景:{current_pkg or 'none'}），進入啟動流程。"
                        )
                    self._transition("A", "launch_game")
            return True

        if self.current_step == "launch_game":
            if self._launch_game():
                if self.bot.mode == "1":
                    self._transition("A", "wait_window")
                else:
                    # EMU 啟動後先暖機，避免過快進入登入流程造成白屏/卡住。
                    self._transition("A", "wait_emu_warmup")
                return True

            if time.time() - self.flow_start_time > 15.0:
                self.bot.log("[DISCONNECT] 無法啟動遊戲，停止腳本。")
                self.bot.stop()
                self.recovery_active = False
                return False
            return True

        if self.current_step == "wait_emu_warmup":
            warmup_elapsed = time.time() - self.flow_start_time
            if warmup_elapsed < self.emu_launch_warmup_seconds:
                self._log_throttled(
                    "flow_a_emu_warmup",
                    (
                        "[FLOW-A] EMU 啟動暖機中"
                        f"（{warmup_elapsed:.1f}/{self.emu_launch_warmup_seconds:.1f}s）。"
                    ),
                    1.0,
                )
                return True
            self.bot.log("[FLOW-A] EMU 啟動暖機完成。")
            if self.login_game_enabled:
                self.bot.log("[FLOW-A] 轉入流程 B（wait_login_scene）。")
                self._transition("B", "wait_login_scene")
            else:
                self.bot.log("[FLOW-A] EMU 已啟動，登入流程停用，恢復主循環。")
                self._finish_recovery()
            return True

        if self.current_step == "wait_window":
            if self._try_attach_launched_pc_window() or self._is_pc_window_valid():
                self._transition("A", "confirm_dialog")
                return True

            if time.time() - self.flow_start_time > self.pc_launch_wait_timeout:
                self.bot.log(
                    f"[FLOW-A] 等待 PC 遊戲視窗重新建立逾時（{self.pc_launch_wait_timeout:.0f}s），停止腳本。"
                )
                self.bot.stop()
                self.recovery_active = False
                return False
            return True

        if self.current_step == "confirm_dialog":
            return self._run_flow_a_confirm_dialog(screen)

        if self.current_step == "confirm_dialog_check":
            return self._run_flow_a_confirm_dialog_check(screen)

        self._transition("A", "close_game")
        return True

    def _close_game(self, screen):
        if self.bot.mode == "1":
            self._close_pc_game(screen)
            return
        self._close_emu_game(screen)

    def _close_pc_game(self, screen):
        if self._can_act():
            try:
                ctypes.windll.user32.PostMessageW(int(self.bot.hwnd), 0x0010, 0, 0)
                self.last_action_time = time.time()
                self._log_throttled("flow_a_close_pc_postmsg", "[FLOW-A] 已嘗試直接關閉 PC 遊戲視窗。", 3.0)
            except Exception as e:
                self.bot.log(f"[FLOW-A] 直接關閉失敗: {e}")

    def _close_emu_game(self, screen):
        package_name = self._resolve_emu_package_name()
        if not package_name:
            self.bot.log("[FLOW-A] EMU 套件名稱未設定，無法直接關閉。")
            return
        if not self._can_act():
            return
        try:
            self.bot.device.shell(f"am force-stop {package_name}")
            self.last_action_time = time.time()
            self._emu_close_attempts += 1
            self._log_throttled(
                "flow_a_emu_force_stop",
                f"[FLOW-A] EMU 直接關閉已送出 force-stop: {package_name}",
                1.0,
            )
        except Exception as e:
            self.bot.log(f"[FLOW-A] EMU 直接關閉失敗: {e}")

    def _run_flow_a_confirm_dialog(self, screen):
        """FLOW-A confirm_dialog 步驟：重開遊戲後偵測確認彈窗。

        若畫面出現 btn_confirm 則點擊。點擊後若遊戲視窗消失（遊戲被關閉），
        根據重連嘗試次數決定是否重新啟動遊戲；若視窗仍在或等候逾時則繼續流程。
        """
        # 記錄整體迴圈起始時間（僅在首次進入時設定）
        if not hasattr(self, '_confirm_dialog_loop_start') or self._confirm_dialog_loop_start is None:
            self._confirm_dialog_loop_start = time.time()

        # 整體逾時 → 不再等待，繼續流程
        if time.time() - self._confirm_dialog_loop_start > 30.0:
            self.bot.log("[FLOW-A] 確認彈窗迴圈逾時，繼續流程。")
            self._confirm_dialog_loop_start = None
            return self._flow_a_proceed_after_window()
        # 優先偵測 update_resource（遊戲更新資源提示）
        if screen is not None and self._click_template(screen, "update_resource"):
            self.bot.log("[FLOW-A] 偵測到遊戲更新資源彈窗，已點擊 btn_confirm。")
            self._transition("A", "confirm_dialog_check")
            return True


        # 偵測並點擊 btn_confirm
        if screen is not None and self._click_template(screen, "btn_confirm"):
            self.bot.log("[FLOW-A] 偵測到確認彈窗，已點擊 btn_confirm。")
            self._transition("A", "confirm_dialog_check")
            return True

        # 等候逾時 → 無彈窗，繼續流程
        if time.time() - self.flow_start_time > 5.0:
            self._confirm_dialog_loop_start = None
            return self._flow_a_proceed_after_window()
        return True

    def _run_flow_a_confirm_dialog_check(self, screen):
        """FLOW-A confirm_dialog_check：點擊 btn_confirm 後檢查遊戲視窗是否仍存在。"""
        # 給遊戲一點時間決定是否關閉
        if time.time() - self.flow_start_time < 2.0:
            return True

        if self.bot.mode == "1" and not self._is_pc_window_valid():
            # 遊戲已關閉 → 根據重連次數決定是否重開
            unlimited = (self.max_reconnect_attempts == 0)
            if not unlimited and self.reconnect_attempts > self.max_reconnect_attempts:
                self.bot.log("[FLOW-A] 確認彈窗後遊戲已關閉且超過重連上限，停止腳本。")
                self.bot.stop()
                self.recovery_active = False
                self._confirm_dialog_loop_start = None
                return False
            self.bot.log("[FLOW-A] 確認彈窗後遊戲已關閉，重新啟動遊戲。")
            self._confirm_dialog_loop_start = None
            self._transition("A", "launch_game")
            return True

        # 視窗仍存在 → 迴圈回 confirm_dialog 繼續偵測
        self.bot.log("[FLOW-A] 視窗仍存在，繼續偵測確認彈窗。")
        self._transition("A", "confirm_dialog")
        return True

    def _flow_a_proceed_after_window(self):
        """FLOW-A 在視窗確認後，進入下一流程。"""
        if self.login_game_enabled:
            self._transition("B", "wait_login_scene")
        else:
            self.bot.log("[FLOW-A] 流程 A 完成，登入遊戲流程已停用，恢復主循環。")
            self._finish_recovery()
        return True

    def _launch_game(self):
        if not self._can_act():
            return False

        if self.bot.mode == "1":
            if not self.pc_exe_path or not os.path.exists(self.pc_exe_path):
                self.bot.log("[FLOW-A] PC EXE 路徑未設定或不存在，無法自動重開。")
                return False

            try:
                self.pc_hwnd_snapshot_before_launch = self._list_candidate_game_hwnds()
                self.pc_prelaunch_exe_pids = self._get_running_exe_pids()
                process = subprocess.Popen([self.pc_exe_path], cwd=os.path.dirname(self.pc_exe_path))
                self.last_action_time = time.time()
                self.pc_launched_pid = int(getattr(process, "pid", 0) or 0)
                self.pc_expected_new_pids = set()
                self.pc_launch_guard_until = time.time() + self.pc_launch_wait_timeout
                self.bot.log(
                    f"[FLOW-A] 已重啟 PC 遊戲，等待最多 {self.pc_launch_wait_timeout:.0f}s 讓視窗建立。"
                )
                return True
            except Exception as e:
                self.bot.log(f"[FLOW-A] 啟動 PC 遊戲失敗: {e}")
                return False

        package_name = self._resolve_emu_package_name()
        if not package_name:
            self.bot.log("[FLOW-A] EMU 套件名稱未設定且自動偵測失敗，無法自動重開。")
            return False

        launched = self._launch_emu_with_monkey(package_name)
        if not launched:
            launched = self._launch_emu_with_am_start(package_name)
        if not launched:
            launched = self._launch_emu_with_ldconsole_runapp(package_name)
        if not launched:
            launched = self._launch_emu_after_instance_wakeup(package_name)

        if launched:
            self.last_action_time = time.time()
        return launched

    def _launch_emu_with_ldconsole_runapp(self, package_name):
        """使用 LDPlayer 控制台 runapp 啟動（不依賴 ADB）。"""
        pkg = str(package_name or "").strip()
        if not pkg:
            return False

        console_path = find_ldplayer_console_path()
        if not console_path:
            self.bot.log("[FLOW-A] 找不到 ldconsole/dnconsole，略過 runapp 啟動。")
            return False

        index = serial_to_ldplayer_index(getattr(self.bot.device, "serial", ""))
        if index is None:
            self.bot.log("[FLOW-A] 無法由 serial 推導 LDPlayer index，略過 runapp 啟動。")
            return False

        try:
            result = subprocess.run(
                [console_path, "runapp", "--index", str(index), "--packagename", pkg],
                capture_output=True,
                text=True,
                timeout=8,
            )
            out = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
            if result.returncode == 0:
                self.bot.log(f"[FLOW-A] 已透過 LDPlayer runapp 啟動 EMU 套件: {pkg}")
                return True
            self.bot.log(f"[FLOW-A] LDPlayer runapp 啟動失敗: {out[:200]}")
            return False
        except Exception as e:
            self.bot.log(f"[FLOW-A] LDPlayer runapp 執行失敗: {e}")
            return False

    def _launch_emu_after_instance_wakeup(self, package_name):
        """喚起 LDPlayer 實例後再次嘗試 runapp。"""
        pkg = str(package_name or "").strip()
        if not pkg:
            return False

        if not self._launch_ldplayer_instance():
            return False

        # 給模擬器短暫時間恢復可用狀態，再送 runapp。
        time.sleep(2.0)
        return self._launch_emu_with_ldconsole_runapp(pkg)

    def _launch_emu_with_monkey(self, package_name):
        pkg = str(package_name or "").strip()
        if not pkg:
            return False
        try:
            out = str(
                self.bot.device.shell(
                    f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1"
                )
                or ""
            )
            low = out.lower()
            if "no activities found" in low or "error" in low or "exception" in low:
                self.bot.log(f"[FLOW-A] monkey 啟動回傳異常，改用 am start。輸出: {out.strip()[:200]}")
                return False
            self.bot.log(f"[FLOW-A] 已透過 monkey 啟動 EMU 套件: {pkg}")
            return True
        except Exception as e:
            self.bot.log(f"[FLOW-A] monkey 啟動 EMU 套件失敗: {e}")
            return False

    def _resolve_emu_launch_activity(self, package_name):
        pkg = str(package_name or "").strip()
        if not pkg:
            return ""
        try:
            out = str(self.bot.device.shell(f"cmd package resolve-activity --brief {pkg}") or "")
        except Exception:
            out = ""

        for raw in out.splitlines():
            line = str(raw or "").strip()
            if not line:
                continue
            if line.startswith("priority=") or line.startswith("ResolveInfo"):
                continue
            if "/" in line:
                return line
        return ""

    def _launch_emu_with_am_start(self, package_name):
        pkg = str(package_name or "").strip()
        if not pkg:
            return False

        component = self._resolve_emu_launch_activity(pkg)
        commands = []
        if component:
            commands.append(f"am start -n {component}")
        commands.append(f"am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -p {pkg}")

        for cmd in commands:
            try:
                out = str(self.bot.device.shell(cmd) or "")
            except Exception as e:
                self.bot.log(f"[FLOW-A] am start 指令失敗: {e}")
                continue

            low = out.lower()
            if "error" in low or "exception" in low:
                self.bot.log(f"[FLOW-A] am start 回傳異常: {out.strip()[:200]}")
                continue

            self.bot.log(f"[FLOW-A] 已透過 am start 啟動 EMU 套件: {pkg}")
            return True

        self.bot.log(f"[FLOW-A] monkey 與 am start 皆無法啟動 EMU 套件: {pkg}")
        return False

    def _resolve_emu_package_name(self):
        if self.emu_package_name:
            return self.emu_package_name
        if self.detected_emu_package_name:
            return self.detected_emu_package_name
        detected = self._detect_foreground_package()
        if detected:
            self.detected_emu_package_name = detected
            self.bot.log(f"[FLOW-A] 自動偵測到 EMU 套件名稱: {detected}")
            return detected
        return ""

    def _is_emu_game_foreground(self, package_name):
        """檢查 EMU 當前前景是否仍是目標遊戲套件。"""
        pkg = str(package_name or "").strip()
        if self.bot.mode != "2" or not pkg:
            return False
        current = self._detect_foreground_package()
        return bool(current) and current.startswith(pkg)

    def _get_emu_foreground_state(self, package_name):
        """回傳 (state, current_pkg): foreground/not_foreground/unknown。"""
        pkg = str(package_name or "").strip()
        if self.bot.mode != "2" or not pkg:
            return "unknown", ""
        current = str(self._detect_foreground_package() or "").strip()
        if not current:
            return "unknown", ""
        if current.startswith(pkg):
            return "foreground", current
        return "not_foreground", current

    def _detect_foreground_package(self):
        if self.bot.mode != "2":
            return ""
        try:
            out = self.bot.device.shell("dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'")
        except Exception:
            out = ""

        package = extract_package_from_text(out)
        if package:
            return package

        try:
            out_top = self.bot.device.shell("dumpsys activity top")
        except Exception:
            out_top = ""
        return extract_package_from_text(out_top)

    def _launch_ldplayer_instance(self):
        console_path = find_ldplayer_console_path()
        if not console_path:
            self.bot.log("[FLOW-A] 找不到 ldconsole/dnconsole，無法喚起模擬器。")
            return False

        index = serial_to_ldplayer_index(getattr(self.bot.device, "serial", ""))
        if index is None:
            self.bot.log("[FLOW-A] 無法由 serial 推導 LDPlayer index。")
            return False

        try:
            subprocess.Popen([console_path, "launch", "--index", str(index)])
            self.bot.log(f"[FLOW-A] 已喚起 LDPlayer index={index}。")
            return True
        except Exception as e:
            self.bot.log(f"[FLOW-A] 喚起 LDPlayer 失敗: {e}")
            return False

    def _run_flow_b(self, screen):
        if not self.login_game_enabled:
            if self.restart_game_enabled:
                self.bot.log("[FLOW-B] 已停用，改走流程 A。")
                self._transition("A", "close_game")
                return True
            self.bot.log("[FLOW-B] 已停用且流程 A 也停用，停止腳本。")
            self.bot.stop()
            self.recovery_active = False
            return False

        elapsed = time.time() - self.flow_start_time
        if elapsed > self.login_timeout:
            self.bot.log("[FLOW-B] 登入流程逾時，切回流程 A 重開。")
            self._transition("A", "close_game")
            return True

        if self._handle_start_game_announcement(screen, "FLOW-B"):
            return True

        # 剛進入流程 B 時，上一幀可能殘留遊戲畫面（btn_power_saving 仍可見），
        # 需等待至少 2 秒讓遊戲響應確認/重連按鈕後畫面切換，避免誤判「已在遊戲內」。
        if elapsed < 2.0:
            self._log_throttled("flow_b_settle_wait", "[FLOW-B] 等待畫面穩定中...", 1.0)
            return True

        if self._has_template(screen, "btn_power_saving"):
            if self.auto_enable_features_enabled:
                self.bot.log("[FLOW-B] 已在遊戲內，進入流程 C（先檢查公告/彈窗）。")
                self._transition("C", "wait_in_game")
                return True
            self.bot.log("[FLOW-B] 已在遊戲內，略過自動開啟功能，恢復主流程。")
            self._finish_recovery()
            return False

        if self.current_step == "wait_login_scene":
            if self._has_template(screen, "multi_login"):
                self.current_step = "login"
            elif self._has_template(screen, "custom_login"):
                self.current_step = "login"
            elif self._has_template(screen, "select_server"):
                self.current_step = "select_server"
            elif self._has_template(screen, "select_character"):
                self.current_step = "select_character"

        if self.current_step in {"wait_login_scene", "login"}:
            if self._has_template(screen, "custom_login"):
                if not self._click_template(screen, "btn_login_account"):
                    self._click_template(screen, "btn_confirm")
                return True

            if self._has_template(screen, "multi_login"):
                self._handle_multi_login(screen, "FLOW-B")
                return True

        if self._has_template(screen, "select_server"):
            if self._click_point(self.server_click_point[0], self.server_click_point[1]):
                self.bot.log("[FLOW-B] 已點擊選服。")
            return True

        if self._has_template(screen, "select_character"):
            self._click_template(screen, "login_game_button")
            return True

        handled, self.last_action_time = handle_post_login_popups(
            self.bot,
            screen,
            "FLOW-B",
            self.last_action_time,
            self.action_cooldown,
            self.bot.log,
        )
        if handled:
            return True

        return True

    def _run_flow_c(self, screen):
        if not self.auto_enable_features_enabled:
            self.bot.log("[FLOW-C] 自動開啟功能已停用，恢復主流程。")
            self._finish_recovery()
            return False

        if self._handle_start_game_announcement(screen, "FLOW-C"):
            return True

        elapsed = time.time() - self.flow_start_time
        if elapsed > self.post_login_timeout:
            self.bot.log("[FLOW-C] 進遊戲後流程逾時，改回流程 B。")
            self._transition("B", "wait_login_scene")
            return True

        # 不論目前在 FLOW-C 哪個步驟，先統一處理登入後彈窗（包含一般公告）。
        handled, self.last_action_time = handle_post_login_popups(
            self.bot,
            screen,
            "FLOW-C",
            self.last_action_time,
            self.action_cooldown,
            self.bot.log,
        )
        if handled:
            return True

        if self.current_step == "wait_in_game":
            if self._is_in_game_screen(screen):
                self._transition("C", "enable_lurk")
            return True

        if self.current_step == "enable_lurk":
            if not self._should_check_auto_feature_scan():
                return True
            if not self.auto_enable_wander:
                self.current_step = "enable_ai"
                return True

            in_battle_scene = self._has_template(screen, "in_battle")

            # 戰鬥中不處理徘徊（避免送出 R 快捷鍵造成其他功能誤觸），直接交給 AI 步驟。
            if in_battle_scene:
                self._log_throttled(
                    "flow_c_wander_skip_in_battle",
                    "[FLOW-C] 戰鬥中略過徘徊步驟，避免快捷鍵干擾。",
                    3.0,
                )
                self.current_step = "enable_ai"
                return True

            if self._has_template(screen, "btn_wander_on"):
                self.current_step = "enable_ai"
                return True

            if self._click_template(screen, "btn_wander_off", cooldown=self.auto_feature_action_cooldown):
                self.bot.log("[FLOW-C] 偵測到徘徊關閉，已嘗試開啟。")
                self.current_step = "enable_ai"
                return True

            if self._can_act_auto_feature():
                self.bot.execute_key("r", android_keycode=46)
                self.last_action_time = time.time()
                self.bot.log("[FLOW-C] 已送出徘徊快捷鍵 R。")
                self.current_step = "enable_ai"
            return True

        if self.current_step == "enable_ai":
            if not self._should_check_auto_feature_scan():
                return True
            if not self.auto_enable_ai:
                self.bot.log("[FLOW-C] AI 自動開啟已停用，恢復主流程。")
                self._finish_recovery()
                return False

            in_battle_scene = self._has_template(screen, "in_battle")
            if in_battle_scene:
                if self._has_template(screen, "btn_ai_off_in_battle"):
                    self._flow_c_ai_off_seen_frames += 1
                    now = time.time()
                    click_cooldown = max(self.auto_feature_action_cooldown * 2.0, 1.2)
                    if self._flow_c_ai_off_seen_frames < 2:
                        self._log_throttled(
                            "flow_c_ai_wait_stable_in_battle",
                            "[FLOW-C] 戰鬥中偵測到 AI 關閉，等待連續命中確認後再點擊。",
                            2.0,
                        )
                        return True
                    if (now - self._flow_c_ai_last_click_at) < click_cooldown:
                        self._log_throttled(
                            "flow_c_ai_click_cooldown",
                            "[FLOW-C] 戰鬥中 AI 重試冷卻中，持續監看。",
                            2.0,
                        )
                        return True
                    if self._click_template(screen, "btn_ai_off_in_battle", cooldown=self.auto_feature_action_cooldown):
                        self._flow_c_ai_last_click_at = time.time()
                        self.bot.log("[FLOW-C] 偵測到戰鬥中 AI 關閉，已嘗試開啟（持續監看模式）。")
                    return True

                self._flow_c_ai_off_seen_frames = 0
                self.bot.log("[FLOW-C] 戰鬥中未見 AI 關閉按鈕，視為 AI 已開啟，恢復主流程。")
                self._finish_recovery()
                return False

            self._flow_c_ai_off_seen_frames = 0

            if time.time() - self.flow_start_time > self.in_game_confirm_timeout:
                self.bot.log("[FLOW-C] AI 狀態確認逾時，先恢復主流程。")
                self._finish_recovery()
                return False

            return True  # 繼續等待 AI 按鈕出現

        self._finish_recovery()
        return False

    def _handle_start_game_announcement(self, screen, flow_tag):
        if not self._has_template(screen, "start_game_announcement"):
            return False

        if self._click_template(screen, "dont_ask_today"):
            self.bot.log(f"[{flow_tag}] 偵測到啟動公告，已先勾選/點擊 dont_ask_today。")

        if getattr(self.bot, "mode", "") == "2":
            if self._can_act():
                self.bot.execute_key("esc", android_keycode=111)
                self.last_action_time = time.time()
                self.bot.log(f"[{flow_tag}] 偵測到啟動公告，已送出 ESC 關閉。")
        elif self._click_template(screen, "btn_cross"):
            self.bot.log(f"[{flow_tag}] 偵測到啟動公告，已點擊關閉。")
        return True

    def _finish_recovery(self):
        if bool(getattr(self.bot, "auto_battle_enabled", False)):
            self.bot.log("[DISCONNECT] 重連流程完成，返回自動對戰主循環。")
        else:
            self.bot.log("[DISCONNECT] 重連流程完成，恢復主循環。")
        self.recovery_active = False
        self.is_disconnected = False
        self.recovery_reason = ""
        self.current_flow = None
        self.current_step = None
        self.flow_start_time = 0.0
        self.last_action_time = 0.0
        self.detected_emu_package_name = ""
        self.pc_launched_pid = 0
        self.pc_prelaunch_exe_pids = set()
        self.pc_expected_new_pids = set()
        self.game_state = GAME_STATE_AFTER_IN_GAME
        self._ai_clicked_on_state3_exit = False
        self._state3_dont_ask_clicked = False
        self._state3_wait_started_at = 0.0
        self._last_auto_feature_check_time = 0.0
        self._state4_not_in_battle_frames = 0
        self._state4_ai_off_seen_frames = 0
        self._state4_ai_last_click_at = 0.0
        self._flow_c_ai_off_seen_frames = 0
        self._flow_c_ai_last_click_at = 0.0
        self._reset_screen_tracking()

    def _transition(self, flow, step):
        self.current_flow = flow
        self.current_step = step
        self.flow_start_time = time.time()
        if flow == "A" and step == "close_game":
            self._reset_scheduled_restart_timer("flow_a_close_game")
            self._emu_close_attempts = 0
            self._emu_close_started_at = self.flow_start_time
            self._emu_not_foreground_since = 0.0
        if flow == "A" and step == "launch_game":
            self._reset_scheduled_restart_timer("flow_a_launch_game")
        if flow == "C":
            self._flow_c_ai_off_seen_frames = 0
            self._flow_c_ai_last_click_at = 0.0

    def _can_act(self):
        return can_act(self.last_action_time, self.action_cooldown)

    def _can_act_auto_feature(self):
        return can_act(self.last_action_time, self.auto_feature_action_cooldown)

    def _should_check_auto_feature_scan(self):
        now = time.time()
        interval = max(0.1, float(self.auto_feature_scan_interval))
        if (now - self._last_auto_feature_check_time) < interval:
            return False
        self._last_auto_feature_check_time = now
        return True

    def _run_periodic_game_open_check(self, screen):
        """全狀態定時檢查遊戲是否開啟；命中時直接切流程 A。"""
        if self.bot is None or self.recovery_active or not self.enabled:
            return False
        if not self._should_check_game_open():
            return False
        if self._is_game_no_longer_open(screen):
            self.bot.log("[DISCONNECT] 定時檢查發現遊戲已關閉，進入流程 A 重開。")
            self._enter_recovery("game_not_open")
            self._transition("A", "close_game")
            return self._run_recovery(screen if isinstance(screen, np.ndarray) else None)
        self._log_throttled("game_open_check_alive", "[DISCONNECT] 定時檢查結果：遊戲仍開啟。", 10.0)
        return False

    def _scheduled_restart_interval_seconds(self):
        total_minutes = (int(self.scheduled_restart_hours) * 60) + int(self.scheduled_restart_minutes)
        return max(60.0, float(total_minutes) * 60.0)

    def _reset_scheduled_restart_timer(self, reason=""):
        self._last_scheduled_restart_ts = time.time()
        if reason:
            self._log_throttled(
                "scheduled_restart_timer_reset",
                f"[DISCONNECT] 定時重開計時器已重置（{reason}）。",
                5.0,
            )

    def _run_scheduled_restart_check(self, screen):
        if self.bot is None or self.recovery_active or not self.enabled:
            return False
        if not self.restart_game_enabled or not self.scheduled_restart_enabled:
            return False

        interval = self._scheduled_restart_interval_seconds()
        now = time.time()
        elapsed = now - float(self._last_scheduled_restart_ts)
        if elapsed < interval:
            remaining = max(0.0, interval - elapsed)
            self._log_throttled(
                "scheduled_restart_wait",
                (
                    "[DISCONNECT] 定時重開等待中："
                    f"剩餘 {remaining:.0f}s（每 {interval / 60.0:.0f} 分鐘重開一次）。"
                ),
                30.0,
            )
            return False

        self.bot.log("[DISCONNECT] 定時重開時間到，進入流程 A 直接重開遊戲。")
        self._enter_recovery("scheduled_restart")
        self._transition("A", "close_game")
        return self._run_recovery(screen if isinstance(screen, np.ndarray) else None)

    def _should_check_game_open(self):
        if self.bot is None:
            return False
        now = time.time()
        mode = str(getattr(self.bot, "mode", ""))
        if str(getattr(self.bot, "mode", "")) == "1":
            interval = max(1.0, float(self.check_game_open_interval_pc)) * 60.0
            last_check = self._last_game_open_check_pc
        else:
            interval = max(1.0, float(self.check_game_open_interval_emu)) * 60.0
            last_check = self._last_game_open_check_emu

        elapsed = now - last_check
        if elapsed < interval:
            remaining = max(0.0, interval - elapsed)
            self._log_throttled(
                "game_open_check_wait",
                (
                    "[STATE-4] 定時檢查遊戲開啟狀態：尚未到達檢查時間"
                    f"（mode={'PC' if mode == '1' else 'EMU'}，剩餘 {remaining:.0f}s）。"
                ),
                30.0,
            )
            return False

        if str(getattr(self.bot, "mode", "")) == "1":
            self._last_game_open_check_pc = now
        else:
            self._last_game_open_check_emu = now

        self.bot.log(
            "[STATE-4] 定時檢查遊戲開啟狀態：開始檢查"
            f"（mode={'PC' if mode == '1' else 'EMU'}，間隔 {interval / 60.0:.0f} 分鐘）。"
        )
        return True

    def _is_game_no_longer_open(self, screen=None):
        if self.bot is None:
            return False
        if str(getattr(self.bot, "mode", "")) == "1":
            is_open = self._is_pc_window_valid()
            self.bot.log(
                f"[STATE-4] 定時檢查結果（PC）：視窗{'存在' if is_open else '不存在'}。"
            )
            return not is_open

        package_name = self._resolve_emu_package_name()
        if not package_name:
            self.bot.log("[STATE-4] 定時檢查結果（EMU）：套件名稱未知，略過本次判定。")
            return False

        fg_state, current_pkg = self._get_emu_foreground_state(package_name)
        self.bot.log(
            "[STATE-4] 定時檢查結果（EMU）："
            f"目標={package_name}，前景={current_pkg or 'unknown'}，狀態={fg_state}。"
        )

        return fg_state == "not_foreground"

    def should_skip_screen_capture(self):
        """在 EMU recovery 的特定步驟略過截圖，避免 screencap 卡住阻斷流程。"""
        if self.bot is None or str(getattr(self.bot, "mode", "")) != "2":
            return False
        if not self.recovery_active:
            return False
        if self.current_flow != "A":
            return False
        return self.current_step in {"close_game", "launch_game", "wait_emu_warmup"}

    def _refresh_bot_identity_with_hwnd(self, hwnd):
        if self.bot is None or str(getattr(self.bot, "mode", "")) != "1":
            return
        try:
            hwnd_int = int(hwnd)
        except Exception:
            return
        self.bot.name = f"PC-{hwnd_int}"
        self.bot.device_id = f"PC-{hwnd_int}"

    def _is_pc_exe_running(self):
        if self.bot is None or str(getattr(self.bot, "mode", "")) != "1":
            return False
        if not self.pc_exe_path:
            return False

        exe_name = os.path.basename(self.pc_exe_path).strip()
        if not exe_name:
            return False

        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {exe_name}"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            output = (result.stdout or "") + "\n" + (result.stderr or "")
            return exe_name.lower() in output.lower()
        except Exception:
            return False

    def _log_throttled(self, key, msg, interval_sec=3.0):
        now = time.time()
        last = float(self._log_throttle_state.get(key, 0.0) or 0.0)
        if now - last >= float(interval_sec):
            self._log_throttle_state[key] = now
            self.bot.log(msg)

    def _has_template(self, screen, key):
        cache_key = (id(screen), key)
        if cache_key in self._frame_template_cache:
            return self._frame_template_cache[cache_key] is not None
        pos = self.bot.find_pos(screen, key)
        self._frame_template_cache[cache_key] = pos
        return pos is not None

    def _handle_pop_gift_after_reconnect(self, screen, tag):
        """按下 btn_reconnect 後先檢查 pop_gift_box，若出現則先送 ESC。"""
        if screen is not None and self._has_template(screen, "pop_gift_box"):
            self.bot.execute_key("esc", android_keycode=111)
            self.last_action_time = time.time()
            self.bot.log(f"[{tag}] btn_reconnect 後偵測到限時禮盒，已送出 ESC。")
            return True

        fresh = self.bot.get_screenshot(use_cache=False)
        if fresh is not None:
            if self._has_template(fresh, "pop_gift_box"):
                self.bot.execute_key("esc", android_keycode=111)
                self.last_action_time = time.time()
                self.bot.log(f"[{tag}] btn_reconnect 後偵測到限時禮盒，已送出 ESC。")
                return True

        return False

    def _click_template(self, screen, key, cooldown=None):
        actual_cooldown = self.action_cooldown if cooldown is None else float(cooldown)
        if not can_act(self.last_action_time, actual_cooldown):
            return False
        cache_key = (id(screen), key)
        if cache_key in self._frame_template_cache:
            pos = self._frame_template_cache[cache_key]
        else:
            pos = self.bot.find_pos(screen, key)
            self._frame_template_cache[cache_key] = pos
        if not pos:
            return False
        self.bot.execute_click(pos[0], pos[1])
        self.last_action_time = time.time()
        return True

    def _click_point(self, x, y):
        clicked, self.last_action_time = click_point(
            self.bot,
            int(x),
            int(y),
            self.last_action_time,
            self.action_cooldown,
        )
        return clicked

    def reset(self):
        """重置斷線狀態"""
        self.is_disconnected = False
        self.reconnect_attempts = 0
        self.recovery_active = False
        self.recovery_reason = ""
        self.current_flow = None
        self.current_step = None
        self.flow_start_time = 0.0
        self.last_action_time = 0.0
        self.no_screen_fail_count = 0
        self.no_screen_last_time = 0.0
        self.pc_launch_guard_until = 0.0
        self.pc_window_lost_retry_cooldown_until = 0.0
        self.pc_launched_pid = 0
        self.pc_hwnd_snapshot_before_launch = set()
        self.pc_prelaunch_exe_pids = set()
        self.pc_expected_new_pids = set()
        self.game_state = GAME_STATE_DISCONNECT
        self._ai_clicked_on_state3_exit = False
        self._state3_dont_ask_clicked = False
        self._state3_wait_started_at = 0.0
        self._last_auto_feature_check_time = 0.0
        self._state4_not_in_battle_frames = 0
        self._state4_ai_off_seen_frames = 0
        self._state4_ai_last_click_at = 0.0
        self._flow_c_ai_off_seen_frames = 0
        self._flow_c_ai_last_click_at = 0.0
        self._log_throttle_state.clear()
        self._emu_close_attempts = 0
        self._emu_close_started_at = 0.0
        self._emu_not_foreground_since = 0.0
        self._reset_screen_tracking()
