"""
多語言系統
"""

import json
import os
from typing import Optional


class I18n:
    """多語言管理器"""
    
    def __init__(self, language: str = "zh_TW"):
        """
        初始化多語言系統
        Args:
            language: 語言代碼 ('zh_TW', 'zh_CN', 'en')
        """
        self.language = language
        self.translations = {}
        self._load_translations()
    
    def _load_translations(self):
        """加載翻譯文件"""
        try:
            json_path = os.path.join(
                os.path.dirname(__file__),
                "localization.json"
            )
            
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.translations = data
            else:
                print(f"[WARN] 找不到翻譯文件: {json_path}")
                self.translations = {"zh_TW": {}}
        except Exception as e:
            print(f"[ERROR] 加載翻譯失敗: {e}")
            self.translations = {"zh_TW": {}}
    
    def get(self, key: str, default: str = "") -> str:
        """
        獲取翻譯字符串
        Args:
            key: 翻譯鍵
            default: 默認值
        
        Returns:
            翻譯後的字符串
        """
        if self.language in self.translations:
            return self.translations[self.language].get(key, default or key)
        
        # 如果當前語言不存在，嘗試返回英文或中文
        for lang in ["en", "zh_TW", "zh_CN"]:
            if lang in self.translations:
                return self.translations[lang].get(key, default or key)
        
        return default or key
    
    def set_language(self, language: str):
        """
        切換語言
        Args:
            language: 語言代碼
        """
        if language in self.translations:
            self.language = language
        else:
            print(f"[WARN] 不支援的語言: {language}")
    
    def get_available_languages(self) -> list:
        """獲取可用的語言列表"""
        return list(self.translations.keys())


# 全局多語言實例
_i18n_instance = None


def init_i18n(language: str = "zh_TW") -> I18n:
    """
    初始化全局多語言系統
    Args:
        language: 語言代碼
    
    Returns:
        I18n 實例
    """
    global _i18n_instance
    _i18n_instance = I18n(language)
    return _i18n_instance


def t(key: str, default: str = "") -> str:
    """
    翻譯函數 (快捷方式)
    Args:
        key: 翻譯鍵
        default: 默認值
    
    Returns:
        翻譯後的字符串
    """
    if _i18n_instance is None:
        init_i18n()
    
    return _i18n_instance.get(key, default)


def get_i18n() -> I18n:
    """獲取全局多語言實例"""
    if _i18n_instance is None:
        init_i18n()
    
    return _i18n_instance


def set_language(language: str):
    """切換語言"""
    i18n = get_i18n()
    i18n.set_language(language)
