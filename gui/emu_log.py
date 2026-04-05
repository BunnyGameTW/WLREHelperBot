"""
gui/emu_log.py
EmuLogMixin - EMU 模式日誌處理 mixin
"""

from queue import Empty

from i18n import t

from gui.shared import LOG_QUEUE


class EmuLogMixin:
    """EMU 模式日誌 mixin：日誌篩選、追加、清除與定時收集"""

    def _log_line_count(self):
        """取得目前日誌行數"""
        return self.log_text.document().blockCount()

    def _selected_log_level(self):
        text = self.log_filter_level_combo.currentText().strip().upper()
        if text in {"", t("log_level_all", "全部").upper(), "ALL", "全部"}:
            return "ALL"
        return text

    def _log_matches_filter(self, msg):
        level = self._selected_log_level()
        if level != "ALL" and f"[{level}" not in msg.upper():
            return False

        keyword = self.log_filter_input.text().strip().lower()
        if keyword and keyword not in msg.lower():
            return False
        return True

    def _refresh_log_view(self):
        self.log_text.clear()
        for line in self.log_history:
            if self._log_matches_filter(line):
                self.log_text.append(line)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def _clear_log_filter(self):
        self.log_filter_level_combo.setCurrentIndex(0)
        self.log_filter_input.clear()
        self._refresh_log_view()

    def _clear_logs(self):
        self.log_history = []
        self.log_text.clear()

    def append_log(self, msg):
        """添加日誌（保留歷史並支援篩選）"""
        self.log_history.append(msg)
        if getattr(self, 'is_debug', False) and len(self.log_history) > 100:
            self.log_history = self.log_history[-100:]
        if len(self.log_history) > 1000:
            self.log_history = self.log_history[-1000:]

        if not self._log_matches_filter(msg):
            return

        debug_mode_on = getattr(self, 'is_debug', False)
        line_limit = 100 if debug_mode_on else 300
        if self._log_line_count() > line_limit:
            if debug_mode_on:
                self.log_history = self.log_history[-100:]
            self._refresh_log_view()
            return

        self.log_text.append(msg)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def collect_logs(self):
        """收集日誌隊列"""
        processed = 0
        max_per_tick = 120
        while True:
            if processed >= max_per_tick:
                break
            try:
                msg = LOG_QUEUE.get_nowait()
                self.append_log(msg)
                processed += 1
            except Empty:
                break

        # 除錯模式：在狀態列顯示 game_state（僅單開模式，多開時不顯示 state 以避免混淆）
        if self.is_debug and self.is_running:
            from core.disconnect_handler import (
                GAME_STATE_DISCONNECT, GAME_STATE_SELECT_CHARACTER,
                GAME_STATE_IN_GAME, GAME_STATE_AFTER_IN_GAME,
            )
            state_names = {
                GAME_STATE_DISCONNECT: "DISCONNECT",
                GAME_STATE_SELECT_CHARACTER: "SELECT_CHARACTER",
                GAME_STATE_IN_GAME: "IN_GAME",
                GAME_STATE_AFTER_IN_GAME: "AFTER_IN_GAME",
            }
            handlers = (
                [h for b in getattr(self.bot_thread, 'bots', []) or []
                 for h in [getattr(b, 'disconnect_handler', None)] if h is not None]
                if self.bot_thread else []
            )
            # 多開時不顯示 state，只顯示單開模式
            if handlers and len(handlers) == 1:
                states = [state_names.get(h.game_state, str(h.game_state)) for h in handlers]
                self.status_label.setText(t("resumed", "執行中") + f"  |  state: {', '.join(states)}")
