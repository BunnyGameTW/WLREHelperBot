"""
gui/pc_log.py
PCLogMixin - PC 模式日誌 mixin
"""

from queue import Empty
from gui.shared import LOG_QUEUE, AUTOPVE_AVAILABLE


class PCLogMixin:
    """PC 模式日誌 mixin"""

    def _log_line_count(self):
        return self.log_text.document().blockCount()

    def _selected_log_level(self):
        idx = self.log_filter_level_combo.currentIndex()
        return "" if idx == 0 else self.log_filter_level_combo.currentText()

    def _log_matches_filter(self, line):
        level = self._selected_log_level()
        keyword = self.log_filter_input.text().strip().lower()
        if level and f"[{level}]" not in line:
            return False
        if keyword and keyword not in line.lower():
            return False
        return True

    def _refresh_log_view(self):
        self.log_text.clear()
        for line in self.log_history:
            if self._log_matches_filter(line):
                self.log_text.append(line)

    def _clear_log_filter(self):
        self.log_filter_level_combo.setCurrentIndex(0)
        self.log_filter_input.clear()
        self._refresh_log_view()

    def _clear_logs(self):
        self.log_history = []
        self.log_text.clear()

    def append_log(self, message):
        self.log_history.append(message)
        if len(self.log_history) > 1000:
            self.log_history = self.log_history[-1000:]
        if self._log_line_count() > 300:
            self._refresh_log_view()
            return
        if self._log_matches_filter(message):
            self.log_text.append(message)

    def collect_logs(self):
        pending = []
        for _ in range(50):
            try:
                pending.append(LOG_QUEUE.get_nowait())
            except Empty:
                break

        if pending:
            for msg in pending:
                self.log_history.append(msg)
            if len(self.log_history) > 1000:
                self.log_history = self.log_history[-1000:]
            self.log_text.setUpdatesEnabled(False)
            try:
                if self._log_line_count() > 300:
                    self._refresh_log_view()
                else:
                    for msg in pending:
                        if self._log_matches_filter(msg):
                            self.log_text.append(msg)
            finally:
                self.log_text.setUpdatesEnabled(True)

        if self.is_debug and self.is_running and len(self.selected_windows) == 1 and self.bot_thread:
            bots = getattr(self.bot_thread, "bots", None)
            if bots:
                try:
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
                    handlers = [
                        h for b in bots
                        for h in [getattr(b, "disconnect_handler", None)]
                        if h is not None
                    ]
                    if handlers and len(handlers) == 1:
                        from i18n import t
                        states = [state_names.get(h.game_state, str(h.game_state)) for h in handlers]
                        self.status_label.setText(t("resumed", "執行中") + f"  |  state: {', '.join(states)}")
                except Exception:
                    pass
