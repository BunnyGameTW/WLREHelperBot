"""Disconnect handler reusable helpers."""

import re
import time
from typing import Callable, Tuple


def can_act(last_action_time: float, action_cooldown: float) -> bool:
    return (time.time() - last_action_time) >= action_cooldown


def has_template(bot, screen, key: str) -> bool:
    return bool(bot.find_pos(screen, key))


def click_template(bot, screen, key: str, last_action_time: float, action_cooldown: float) -> Tuple[bool, float]:
    if not can_act(last_action_time, action_cooldown):
        return False, last_action_time

    pos = bot.find_pos(screen, key)
    if not pos:
        return False, last_action_time

    bot.execute_click(pos[0], pos[1])
    return True, time.time()


def click_point(bot, x: int, y: int, last_action_time: float, action_cooldown: float) -> Tuple[bool, float]:
    if not can_act(last_action_time, action_cooldown):
        return False, last_action_time

    bot.execute_click(int(x), int(y))
    return True, time.time()


def handle_post_login_popups(
    bot,
    screen,
    flow_tag: str,
    last_action_time: float,
    action_cooldown: float,
    log_func: Callable[[str], None],
) -> Tuple[bool, float]:
    """點擊 login_game_button 後，先處理限時禮盒，再處理啟動公告與一般公告。"""
    if has_template(bot, screen, "pop_gift_box"):
        # 限時禮盒 ESC 使用獨立 1 秒節流，避免短時間連送 ESC 導致畫面卡住。
        now = time.time()
        last_pop_gift_esc = float(getattr(bot, "_last_pop_gift_esc_time", 0.0) or 0.0)
        if (now - last_pop_gift_esc) >= 1.0 and can_act(last_action_time, action_cooldown):
            bot.execute_key("esc", android_keycode=111)
            last_action_time = now
            setattr(bot, "_last_pop_gift_esc_time", now)
            log_func(f"[{flow_tag}] 偵測到限時禮盒，已送出 ESC。")
        return True, last_action_time

    if has_template(bot, screen, "start_game_announcement"):
        if str(getattr(bot, "mode", "")) == "2":
            if can_act(last_action_time, action_cooldown):
                bot.execute_key("esc", android_keycode=111)
                last_action_time = time.time()
                log_func(f"[{flow_tag}] 偵測到啟動公告，已送出 ESC 關閉。")
        else:
            clicked, last_action_time = click_template(
                bot, screen, "btn_cross", last_action_time, action_cooldown
            )
            if clicked:
                log_func(f"[{flow_tag}] 偵測到啟動公告，已點擊關閉。")
        return True, last_action_time

    if has_template(bot, screen, "announcement"):
        if has_template(bot, screen, "dont_ask_today"):
            if flow_tag == "STATE-3" and bool(getattr(bot, "_state3_dont_ask_clicked", False)):
                log_func(f"[{flow_tag}] 偵測到公告彈窗且 dont_ask_today 已於本狀態點擊，略過重複點擊。")
            else:
                clicked, last_action_time = click_template(
                    bot, screen, "dont_ask_today", last_action_time, action_cooldown
                )
                if clicked:
                    if flow_tag == "STATE-3":
                        setattr(bot, "_state3_dont_ask_clicked", True)
                    log_func(f"[{flow_tag}] 偵測到公告彈窗，已先點擊 dont_ask_today。")
                else:
                    log_func(f"[{flow_tag}] 偵測到公告彈窗且有 dont_ask_today，等待可點擊後再關閉。")
                return True, last_action_time

            # STATE-3 已點過 dont_ask_today 後，直接進入關閉流程。
            if str(getattr(bot, "mode", "")) == "2":
                if can_act(last_action_time, action_cooldown):
                    bot.execute_key("esc", android_keycode=111)
                    last_action_time = time.time()
                    log_func(f"[{flow_tag}] 偵測到公告彈窗，已送出 ESC 關閉。")
            else:
                clicked, last_action_time = click_template(
                    bot, screen, "btn_cross", last_action_time, action_cooldown
                )
                if clicked:
                    log_func(f"[{flow_tag}] 偵測到公告彈窗，已點擊 btn_cross 關閉。")
            return True, last_action_time

        if str(getattr(bot, "mode", "")) == "2":
            if can_act(last_action_time, action_cooldown):
                bot.execute_key("esc", android_keycode=111)
                last_action_time = time.time()
                log_func(f"[{flow_tag}] 偵測到公告彈窗，已送出 ESC 關閉。")
        else:
            clicked, last_action_time = click_template(
                bot, screen, "btn_cross", last_action_time, action_cooldown
            )
            if clicked:
                log_func(f"[{flow_tag}] 偵測到公告彈窗，已點擊 btn_cross 關閉。")
        return True, last_action_time

    return False, last_action_time


def extract_package_from_text(text: str) -> str:
    raw = str(text or "")
    if not raw:
        return ""

    patterns = [
        r"([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+)/[a-zA-Z0-9_.$]+",
        r"packageName=([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+)",
    ]
    blocked = {
        "com.android.systemui",
        "com.android.launcher",
        "com.google.android.permissioncontroller",
    }

    for pattern in patterns:
        matches = re.findall(pattern, raw)
        for pkg in matches:
            if pkg.startswith("com.android") or pkg in blocked:
                continue
            return pkg

    return ""


def serial_to_ldplayer_index(serial: str):
    text = str(serial or "")

    m = re.match(r"^emulator-(\d+)$", text)
    if m:
        port = int(m.group(1))
        if port >= 5554 and (port - 5554) % 2 == 0:
            return (port - 5554) // 2

    m = re.match(r"^[^:]+:(\d+)$", text)
    if m:
        port = int(m.group(1))
        if port >= 5555 and (port - 5555) % 2 == 0:
            return (port - 5555) // 2

    return None
