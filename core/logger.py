"""
日誌系統 - LOG_QUEUE 管理與 bot_log
"""
import time

# 全局日誌隊列（需要與 GUI 同步）
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


def bot_log(tag, message, level="INFO"):
    """
    統一的日誌函數
    Args:
        tag: 日誌標籤 (如 "START", "BATTLE", "ENERGY" 等)
        message: 日誌消息
        level: 日誌級別 (INFO, WARN, ERROR 等，默認 INFO)
    """
    timestamp = time.strftime("%H:%M:%S")
    log_msg = f"[{timestamp}] [{tag}] {message}"

    # 發送到隊列（供 GUI 使用）
    if LOG_QUEUE:
        try:
            LOG_QUEUE.put_nowait(log_msg)
        except Exception:
            pass

    # 同時輸出到控制台（GUI 模式下避免重複）
    if not RUNNING_FROM_GUI:
        print(log_msg, flush=True)
