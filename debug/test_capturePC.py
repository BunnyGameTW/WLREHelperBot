import win32gui, win32ui, win32con, ctypes
import cv2
import numpy as np

# 設置 DPI 感知，防止在 Windows 縮放 125% 或 150% 時截圖不準
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    ctypes.windll.user32.SetProcessDPIAware()

def capture_pc_window(window_title):
    # 1. 尋找視窗句柄
    hwnd = win32gui.FindWindow(None, window_title)
    
    if not hwnd:
        print(f"❌ 找不到視窗標題為 '{window_title}' 的程式，請確認遊戲已開啟。")
        return

    # 2. 獲取視窗範圍
    left, top, right, bot = win32gui.GetWindowRect(hwnd)
    w = right - left
    h = bot - top
    print(f"✅ 找到視窗！位置:({left}, {top}), 尺寸:{w}x{h}")

    # 3. 建立設備內存 (Device Context)
    hwndDC = win32gui.GetWindowDC(hwnd)
    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()

    # 4. 建立點陣圖物件
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
    saveDC.SelectObject(saveBitMap)

    # 5. 使用 PrintWindow 抓取畫面 (即便視窗被遮擋有時也能抓到，視後台設置而定)
    # 參數 3 代表抓取整個視窗（含標題列）
    result = ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)

    # 6. 轉化為 OpenCV 格式
    bmpstr = saveBitMap.GetBitmapBits(True)
    img = np.frombuffer(bmpstr, dtype='uint8').reshape((h, w, 4)) # 預設是 BGRA

    # 釋放資源 (這步很重要，不然會記憶體洩漏)
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)

    if result == 1:
        # 轉換顏色空間 BGRA -> BGR
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        # 存檔
        file_name = "debug_screenPC.png"
        cv2.imwrite(file_name, img)
        print(f"💾 PC版截圖成功！已儲存為 '{file_name}'")
        
        # 顯示预览
        cv2.imshow("PC Window Capture Test", img)
        print("💡 按下任意鍵可關閉預覽視窗。")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        print("❌ 截圖失敗，無法獲取視窗像素。")

if __name__ == "__main__":
    # 請確保這串字跟你遊戲視窗左上角的字一模一樣
    target_title = "飄流幻境Re:星之方舟" 
    capture_pc_window(target_title)