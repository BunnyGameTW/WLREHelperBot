"""
gui/shared.py
共用工具模組 - 供 EMU/PC launcher mixin 共用的工具函式、常數與套件初始化
"""

import sys
import os
import warnings
from queue import Queue

warnings.filterwarnings("ignore", category=DeprecationWarning)
try:
    import PyQt5.sip
    if hasattr(PyQt5.sip, 'setdestroyonexit'):
        PyQt5.sip.setdestroyonexit(False)
except Exception:
    pass

# 載入 autoPVE 核心模組
try:
    import autoPVE
    AUTOPVE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Cannot import autoPVE: {e}")
    AUTOPVE_AVAILABLE = False
    autoPVE = None  # type: ignore[assignment]

LOG_QUEUE: Queue = Queue(maxsize=1000)


def resource_path(relative_path: str) -> str:
    """取得資源絕對路徑（支援 PyInstaller 打包環境）"""
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)


def get_app_version() -> str:
    """讀取版本號（優先 VERSION 檔）"""
    try:
        with open(resource_path("VERSION"), "r", encoding="utf-8") as f:
            version = f.read().strip()
            if version:
                return version
    except Exception:
        pass
    return "0.1.0"


APP_VERSION: str = get_app_version()


def build_template_tooltip_html(template_key: str) -> str:
    """為模板辨識閾值欄位產生含圖預覽的 tooltip HTML"""
    filename = f"{template_key}.png"
    image_path = resource_path(os.path.join("templates", filename))
    if os.path.exists(image_path):
        image_src = image_path.replace("\\", "/")
        return f"<b>{filename}</b><br><img src='{image_src}' width='220'>"
    return filename
