#!/usr/bin/env python3
"""
CMD 模式 - 命令行版本
支持 PC 和 EMU 模式，使用 autoPVE 核心邏輯執行自動對戰
"""

import sys
import os
import signal

# 確保能找到 autoPVE 模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import autoPVE
    AUTOPVE_AVAILABLE = True
except ImportError as e:
    print(f"[ERROR] 無法載入 autoPVE 核心模組: {e}")
    AUTOPVE_AVAILABLE = False


def get_app_version():
    """?取版本號"""
    try:
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base, "VERSION"), "r", encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                return v
    except Exception:
        pass
    return "0.1.0"


APP_VERSION = get_app_version()


def _handle_sigint(_signum, _frame):
    """將 Ctrl+C 轉為乾淨退出，避免關閉階段噴 threading KeyboardInterrupt。"""
    print("\n[INFO] 已退出")
    raise SystemExit(0)


def print_header(title):
    """印標題"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def print_menu():
    """印菜單"""
    print(f"""
【模式選擇】
1. PC 模式      - 控制本地遊戲窗口（使用 pydirectinput）
2. EMU 模式     - 控制多個模擬器設備（使用 ADB）
Q. 退出

【執行中快捷鍵】
Ctrl+D  - 開啟/關閉除錯模式
Ctrl+P  - 暂停/繼續偵測
Ctrl+C  - 停止腳本
    """)


def pc_mode():
    """PC 模式 - 使用 autoPVE 核心邏輯"""
    if not AUTOPVE_AVAILABLE:
        print("[ERROR] autoPVE 核心模組不可用，無法啟動 PC 模式")
        return

    print_header("PC 模式 - 命令行版本")
    try:
        autoPVE.main(from_gui=False, mode_override="1")
    except KeyboardInterrupt:
        print("\n[INFO] PC 模式已停止")
    except Exception as e:
        print(f"[ERROR] PC 模式執行失敗: {e}")


def emu_mode():
    """EMU 模式 - 使用 autoPVE 核心邏輯"""
    if not AUTOPVE_AVAILABLE:
        print("[ERROR] autoPVE 核心模組不可用，無法啟動 EMU 模式")
        return

    print_header("EMU 模式 - 命令行版本")
    try:
        autoPVE.main(from_gui=False, mode_override="2")
    except KeyboardInterrupt:
        print("\n[INFO] EMU 模式已停止")
    except Exception as e:
        print(f"[ERROR] EMU 模式執行失敗: {e}")


def main():
    """主菜單"""
    signal.signal(signal.SIGINT, _handle_sigint)
    print_header(f"女王的飄流小助手 - CMD 模式  v{APP_VERSION}")

    if not AUTOPVE_AVAILABLE:
        print("[ERROR] autoPVE 核心模組無法載入，CMD 模式無法使用。")
        print("[INFO] 請確認 autoPVE.py 是否存在且所有依賴已安裝。")
        try:
            input("\n按 Enter 退出...")
        except (KeyboardInterrupt, EOFError):
            pass
        sys.exit(1)

    while True:
        print_menu()

        try:
            choice = input("[INPUT] 選擇 [1/2/Q]: ").strip().upper()
        except KeyboardInterrupt:
            print("\n[INFO] 已退出")
            sys.exit(0)
        except EOFError:
            print("\n[INFO] 未偵測到可用輸入（EOF），已退出")
            sys.exit(0)

        if choice == "1":
            pc_mode()
        elif choice == "2":
            emu_mode()
        elif choice == "Q":
            print("[INFO] 已退出")
            sys.exit(0)
        else:
            print("[ERROR] 選擇無效，請重新選擇\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # 最後保險：避免在 Python 關閉階段顯示 threading KeyboardInterrupt traceback。
        print("\n[INFO] 已退出")
        raise SystemExit(0)
