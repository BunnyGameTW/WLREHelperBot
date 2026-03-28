"""
core 套件 - 自動對戰核心模組
將 autoPVE.py 拆分為獨立子模組，方便維護與擴展。

模組結構:
  constants.py          - 純常數與 resource_path
  logger.py             - 日誌系統 (LOG_QUEUE, bot_log)
  state.py              - 執行時全域狀態 (DEBUG_MODE, PAUSED, LOCK)
  config.py             - 配置載入/儲存 (DEFAULT_CONFIG, RUNNING_CONFIG)
  templates.py          - 模板載入
  performance.py        - 性能監測
  device_utils.py       - 設備偵測與命名 (LDPlayer, ADB, PC 視窗)
  bot.py                - DriftBot 主執行緒類別
  disconnect_handler.py - 斷線偵測接口 (預留)
"""

# 從各子模組匯出常用 API，保持向後相容
from .constants import (
    BASE_W, BASE_H, WINDOW_TITLE, THRESHOLD,
    TEMPLATES_PATHS, CONFIG_FILE_PC, CONFIG_FILE_EMU,
    resource_path,
)
from .logger import (
    bot_log, set_log_queue, set_cmd_input_enabled,
    LOG_QUEUE, CMD_INPUT_ENABLED, RUNNING_FROM_GUI,
)
from .state import (
    DEBUG_MODE, PAUSED, LOCK, PC_WINDOWS,
    set_debug_mode, set_paused,
)
from .config import (
    DEFAULT_CONFIG, RUNNING_CONFIG,
    load_default_config, get_config_file, deep_update,
    load_config, setup_device_configs, log_device_configs,
)
from .templates import load_templates, LOADED_TEMPLATES
from .performance import PerformanceMonitor
from .device_utils import (
    connect_adb, find_pc_game_windows, input_listener,
    get_device_display_name, get_device_custom_name, get_device_model_name,
    find_ldplayer_console_path, get_ldplayer_instances,
    get_ldplayer_custom_name_by_serial, get_ldplayer_custom_names,
)
from .bot import DriftBot
from .disconnect_handler import DisconnectHandler
