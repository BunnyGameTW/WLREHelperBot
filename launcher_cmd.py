#!/usr/bin/env python3
"""
CMD 模式 - 命令行版本
支持 PC 和 EMU 模式，使用 autoPVE 核心邏輯執行自動對戰
"""

import sys
import os

# 確保能找到 autoPVE 模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import autoPVE
    AUTOPVE_AVAILABLE = True
except ImportError as e:
    print(f"[ERROR] 無法載入 autoPVE 核心模組: {e}")
    AUTOPVE_AVAILABLE = False


def print_header(title):
    """印標題"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def print_menu():
    """印菜單"""
    print("""
【模式選擇】
1. PC 模式      - 控制本地遊戲窗口（使用 pydirectinput）
2. EMU 模式     - 控制多個模擬器設備（使用 ADB）
3. 自動選擇     - 進入互動模式自行選擇
Q. 退出

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


def interactive_mode():
    """互動模式 - 不預設模式，由 autoPVE 自行詢問"""
    if not AUTOPVE_AVAILABLE:
        print("[ERROR] autoPVE 核心模組不可用")
        return

    try:
        autoPVE.main(from_gui=False)
    except KeyboardInterrupt:
        print("\n[INFO] 已停止")
    except Exception as e:
        print(f"[ERROR] 執行失敗: {e}")


def main():
    """主菜單"""
    print_header("女王化身為無情的戰爭機器 小助手 - CMD 模式")

    if not AUTOPVE_AVAILABLE:
        print("[ERROR] autoPVE 核心模組無法載入，CMD 模式無法使用。")
        print("[INFO] 請確認 autoPVE.py 是否存在且所有依賴已安裝。")
        input("\n按 Enter 退出...")
        sys.exit(1)

    while True:
        print_menu()

        try:
            choice = input("[INPUT] 選擇 [1/2/3/Q]: ").strip().upper()
        except KeyboardInterrupt:
            print("\n[INFO] 已退出")
            sys.exit(0)

        if choice == "1":
            pc_mode()
        elif choice == "2":
            emu_mode()
        elif choice == "3":
            interactive_mode()
        elif choice == "Q":
            print("[INFO] 已退出")
            sys.exit(0)
        else:
            print("[ERROR] 選擇無效，請重新選擇\n")


if __name__ == "__main__":
    main()
