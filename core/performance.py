"""
性能監測類
"""
import time
from collections import deque


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
        screenshot_avg = (
            sum(self.screenshot_times) / len(self.screenshot_times)
            if self.screenshot_times else 0
        )
        template_avg = (
            sum(self.template_match_times) / len(self.template_match_times)
            if self.template_match_times else 0
        )
        return {
            "fps": frame_fps,
            "frame_ms": frame_avg * 1000,
            "screenshot_ms": screenshot_avg * 1000,
            "template_ms": template_avg * 1000,
        }

    def should_report(self):
        now = time.time()
        if now - self.last_report >= self.report_interval:
            self.last_report = now
            return True
        return False
