import cv2
import numpy as np
from ppadb.client import Client as AdbClient

def diagnostic():
    client = AdbClient(host="127.0.0.1", port=5037)
    devices = client.devices()
    
    if not devices:
        print("❌ 找不到設備，請檢查 adb devices 是否有東西")
        return

    device = devices[0]
    print(f"✅ 已連線到: {device.serial}，正在嘗試截圖...")

    # 取得截圖
    image_bytes = device.screencap()
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)

    if img is not None:
        print(f"📸 截圖成功！尺寸為: {img.shape[1]}x{img.shape[0]}")
        # 將抓到的圖存下來讓你檢查
        cv2.imwrite("debug_screen.png", img)
        print("💾 已儲存診斷圖片為 'debug_screen.png'，請打開看看是不是遊戲畫面。")
        
        # 顯示圖片 (按任意鍵關閉)
        cv2.imshow("ADB Capture Test", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        print("❌ 截圖失敗，抓到的是空數據。")

if __name__ == "__main__":
    diagnostic()