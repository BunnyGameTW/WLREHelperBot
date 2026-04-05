"""
模板 (Template) 載入
"""
import os
import cv2

from .constants import TEMPLATES_PATHS, resource_path
from .logger import bot_log

# 已載入的模板快取
LOADED_TEMPLATES = {}


def _is_complete_png_file(path):
    """快速檢查 PNG 檔案是否完整（至少包含合法 IEND chunk）。"""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception:
        return False

    # PNG signature
    if len(data) < 8 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return False

    offset = 8
    size = len(data)
    while offset + 8 <= size:
        length = int.from_bytes(data[offset:offset + 4], "big", signed=False)
        chunk_type = data[offset + 4:offset + 8]
        offset += 8

        # chunk data + crc
        if offset + length + 4 > size:
            return False

        offset += length + 4
        if chunk_type == b"IEND":
            return True

    return False


def load_templates():
    """載入共用模板圖片"""
    LOADED_TEMPLATES.clear()

    folder = resource_path("templates")
    if not os.path.exists(folder):
        folder = os.path.join(os.path.abspath("."), "templates")
    bot_log("FOLDER", f"正在載入 {folder} 資料夾內的模板...")

    if not os.path.exists(folder):
        os.makedirs(folder)
        bot_log("WARN", f"找不到 {folder} 資料夾，已自動建立。請放入截圖！")

    for key, filename in TEMPLATES_PATHS.items():
        path = os.path.join(folder, filename)
        if os.path.exists(path):
            # 先做完整性檢查，避免 libpng 對損壞 PNG 輸出錯誤並污染日誌。
            if filename.lower().endswith(".png") and not _is_complete_png_file(path):
                bot_log("ERROR", f"PNG 檔案不完整，已略過: {filename}")
                continue

            try:
                img = cv2.imread(path)
            except Exception as e:
                bot_log("ERROR", f"讀取模板失敗 {filename}: {e}")
                continue

            if img is not None:
                LOADED_TEMPLATES[key] = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                bot_log("OK", f"成功載入: {filename}")
            else:
                bot_log("ERROR", f"模板讀取失敗(可能檔案損壞): {filename}")
        else:
            bot_log("ERROR", f"缺檔: {path}")
