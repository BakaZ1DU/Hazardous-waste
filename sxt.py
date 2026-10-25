import cv2
import numpy as np

# 打开电脑自带摄像头
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("❌ 找不到摄像头，请检查设备")
    exit()

print("✅ 摄像头已启动，开始识别画面亮度...")
print("按 'q' 键退出")

while True:
    # 读取一帧画面
    ret, frame = cap.read()
    if not ret:
        print("❌ 读取画面失败")
        break

    # 转成灰度图，计算平均亮度
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    avg_brightness = np.mean(gray)

    # 根据亮度判断画面类型
    if avg_brightness > 180:
        print(f"💡 高亮画面（桌面/白底窗口）- 亮度: {avg_brightness:.1f}")
    elif avg_brightness > 110:
        print(f"⚡ 正常画面（软件/网页）- 亮度: {avg_brightness:.1f}")
    elif avg_brightness > 50:
        print(f"🎮 中等亮度画面（游戏/视频）- 亮度: {avg_brightness:.1f}")
    else:
        print(f"🌙 深色画面（暗色界面/黑夜）- 亮度: {avg_brightness:.1f}")

    # 显示画面窗口
    cv2.imshow("画面预览", frame)

    # 按 'q' 键退出
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 释放资源
cap.release()
cv2.destroyAllWindows()
