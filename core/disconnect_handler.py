"""
斷線偵測處理器 (預留接口)

未來可在此實作:
  - 偵測「連線中斷」或「伺服器斷線」畫面
  - 自動重新登入
  - 回到大廳後恢復自動對戰

使用方式:
  在 DriftBot.run() 主循環中呼叫 handler.check(screen)，
  若回傳 True 表示正在處理斷線，主循環應 continue 跳過本幀。
"""


class DisconnectHandler:
    """
    斷線偵測與自動重連處理器。

    目前為空殼接口，之後實作時只需：
      1. 在 templates/ 加入斷線畫面的模板圖片
      2. 在 constants.py 的 TEMPLATES_PATHS 加入對應 key
      3. 實作 check() 中的偵測與重連邏輯
    """

    def __init__(self, bot=None):
        self.bot = bot
        self.is_disconnected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

    def check(self, screen):
        """
        檢查當前畫面是否為斷線狀態。

        Args:
            screen: 當前截圖 (numpy ndarray)

        Returns:
            True  - 正在處理斷線，主循環應跳過本幀
            False - 連線正常，繼續正常流程
        """
        # TODO: 實作斷線偵測邏輯
        # 範例:
        #   pos = self.bot.find_pos(screen, "disconnect_dialog")
        #   if pos:
        #       self.is_disconnected = True
        #       return self._handle_reconnect(screen)
        return False

    def _handle_reconnect(self, screen):
        """
        處理重新連線流程 (預留)。

        Returns:
            True  - 仍在重連中
            False - 重連完成或放棄
        """
        # TODO: 實作自動重連
        # 範例:
        #   self.reconnect_attempts += 1
        #   if self.reconnect_attempts > self.max_reconnect_attempts:
        #       self.bot.log("[DISCONNECT] 超過重連上限，停止。")
        #       self.bot.stop()
        #       return False
        #   # 點擊重連按鈕...
        #   return True
        return False

    def reset(self):
        """重置斷線狀態"""
        self.is_disconnected = False
        self.reconnect_attempts = 0
