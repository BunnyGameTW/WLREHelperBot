"""
模板 (Template) 載入
"""
import os
import cv2

from .constants import TEMPLATES_PATHS, resource_path
from .logger import bot_log

# 已載入的模板快取
LOADED_TEMPLATES = {}


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
            img = cv2.imread(path)
            if img is not None:
                LOADED_TEMPLATES[key] = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                bot_log("OK", f"成功載入: {filename}")
        else:
            bot_log("ERROR", f"缺檔: {path}")
