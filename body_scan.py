import cv2
import numpy as np
import time
import os
import urllib.request
import sys
import random
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe import Image, ImageFormat
from ultralytics import YOLO

# ===================== 调优参数 =====================
YOLO_IMGSZ = 224
DETECT_INTERVAL = 10
CONF_THRESHOLD = 0.45
CUP_CONF_THRESHOLD = 0.30
PHONE_CONF_THRESHOLD = 0.65
USE_LITE_POSE = True
HANDS_DETECT_INTERVAL = 2
FPS_UPDATE_INTERVAL = 0.25

# ---- 手部判定阈值（专为“4”优化） ----
FINGER_Y_THRESHOLD = 0.035
THUMB_DIST_THRESHOLD = 0.08
THUMB_X_THRESHOLD = 0.03
THUMB_Z_THRESHOLD = 0.02
FINGER_MIN_DIST = 0.03
THUMB_INDEX_DIST_THRESHOLD = 0.06      # 降低，更敏感
THUMB_MCP_PALM_DIST_THRESHOLD = 0.055  # 降低，使拇指更易判定为收起
THUMB_TIP_PALM_DIST_THRESHOLD = 0.075  # 新增：拇指指尖到手掌中心的距离阈值
# =================================================

class HumanActionRecognizer:
    def __init__(self, pose_model='pose_landmarker_lite.task' if USE_LITE_POSE else 'pose_landmarker_heavy.task',
                 hand_model='hand_landmarker.task'):
        self.pose_model_path = self.ensure_model(pose_model)
        self.hand_model_path = self.ensure_model(hand_model)
        self.detect_interval = DETECT_INTERVAL
        self.yolo_imgsz = YOLO_IMGSZ
        self.conf_threshold = CONF_THRESHOLD
        self.cup_conf_threshold = CUP_CONF_THRESHOLD
        self.phone_conf_threshold = PHONE_CONF_THRESHOLD
        self.hands_interval = HANDS_DETECT_INTERVAL
        self.fps_update_interval = FPS_UPDATE_INTERVAL

        # ---- MediaPipe Pose ----
        pose_base_options = python.BaseOptions(model_asset_path=self.pose_model_path)
        pose_options = vision.PoseLandmarkerOptions(
            base_options=pose_base_options,
            output_segmentation_masks=False,
            running_mode=vision.RunningMode.VIDEO,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.pose_detector = vision.PoseLandmarker.create_from_options(pose_options)

        # ---- MediaPipe Hands ----
        hand_base_options = python.BaseOptions(model_asset_path=self.hand_model_path)
        hand_options = vision.HandLandmarkerOptions(
            base_options=hand_base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.hand_detector = vision.HandLandmarker.create_from_options(hand_options)

        self.LANDMARKS = {
            'nose': 0,
            'left_shoulder': 11,
            'right_shoulder': 12,
            'left_elbow': 13,
            'right_elbow': 14,
            'left_wrist': 15,
            'right_wrist': 16,
            'left_hip': 23,
            'right_hip': 24,
            'left_knee': 25,
            'right_knee': 26,
            'left_ankle': 27,
            'right_ankle': 28
        }

        self.yolo = YOLO('yolov8n.pt')
        print(f"YOLO 运行在 CPU，输入尺寸 {self.yolo_imgsz}，检测间隔 {self.detect_interval} 帧")
        print(f"置信度: 普通 {self.conf_threshold}, 杯子 {self.cup_conf_threshold}, 手机 {self.phone_conf_threshold}")
        print(f"手部检测间隔: {self.hands_interval} 帧")

        self.allowed_items = [
            'cup', 'bottle', 'cell phone', 'book', 'remote',
            'keyboard', 'mouse', 'laptop', 'tv', 'scissors',
            'knife', 'fork', 'spoon'
        ]
        self.cached_detections = []
        self.frame_counter = 0
        self.hands_frame_counter = 0
        self.cached_hands = []

        self.fps_counter = 0
        self.fps_start_time = time.time()
        self.display_fps = 0.0

    def ensure_model(self, model_name):
        if os.path.exists(model_name):
            print(f"✓ 找到模型文件: {model_name}")
            return model_name
        print(f"⚠ 未找到模型文件 {model_name}，开始下载...")
        if model_name == 'hand_landmarker.task':
            url = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
        else:
            base = model_name.split('.')[0]
            url = f"https://storage.googleapis.com/mediapipe-models/pose_landmarker/{base}/float16/1/{model_name}"
        try:
            urllib.request.urlretrieve(url, model_name)
            print(f"✓ 模型下载成功: {model_name}")
            return model_name
        except Exception as e:
            print(f"✗ 自动下载失败: {e}")
            print(f"请手动下载模型文件 {model_name} 并放置于当前目录")
            print(f"下载地址: {url}")
            sys.exit(1)

    # ---- 手势识别（针对“4”手势优化） ----
    def get_hand_gesture(self, hand_landmarks):
        if not hand_landmarks:
            return "未检测到手"

        finger_tips = [4, 8, 12, 16, 20]
        finger_pips = [2, 6, 10, 14, 18]

        palm_indices = [0, 5, 9, 13, 17]
        palm_center = np.mean([[hand_landmarks[i].x, hand_landmarks[i].y, hand_landmarks[i].z] for i in palm_indices], axis=0)

        extended = []
        for tip_id, pip_id in zip(finger_tips, finger_pips):
            tip = hand_landmarks[tip_id]
            pip = hand_landmarks[pip_id]
            if tip_id == 4:  # 拇指
                dist = np.hypot(tip.x - pip.x, tip.y - pip.y)
                x_diff = abs(tip.x - pip.x)
                z_diff = abs(tip.z - pip.z)
                if (dist > THUMB_DIST_THRESHOLD and
                    x_diff > THUMB_X_THRESHOLD and
                    z_diff > THUMB_Z_THRESHOLD):
                    extended.append(1)
                else:
                    extended.append(0)
            else:
                if tip.y < pip.y - FINGER_Y_THRESHOLD:
                    extended.append(1)
                else:
                    extended.append(0)

        # ---- 拇指收起判定增强 ----
        if extended[0] == 1:
            thumb_mcp = hand_landmarks[2]  # MCP关节
            thumb_tip = hand_landmarks[4]  # 指尖
            # 条件1：MCP到手掌中心距离小于阈值
            dist_mcp_palm = np.hypot(thumb_mcp.x - palm_center[0], thumb_mcp.y - palm_center[1])
            # 条件2：指尖到手掌中心距离小于阈值（辅助）
            dist_tip_palm = np.hypot(thumb_tip.x - palm_center[0], thumb_tip.y - palm_center[1])
            if dist_mcp_palm < THUMB_MCP_PALM_DIST_THRESHOLD or dist_tip_palm < THUMB_TIP_PALM_DIST_THRESHOLD:
                extended[0] = 0

        # ---- 拇指-食指距离抑制（补充） ----
        if extended[0] == 1:
            thumb_tip = hand_landmarks[4]
            index_tip = hand_landmarks[8]
            dist_thumb_index = np.hypot(thumb_tip.x - index_tip.x, thumb_tip.y - index_tip.y)
            if dist_thumb_index < THUMB_INDEX_DIST_THRESHOLD:
                extended[0] = 0

        # ---- 手指间距过滤 ----
        for i in range(1, 5):
            if extended[i] == 1:
                tip_i = hand_landmarks[finger_tips[i]]
                if i > 1:
                    tip_prev = hand_landmarks[finger_tips[i-1]]
                    dist = np.hypot(tip_i.x - tip_prev.x, tip_i.y - tip_prev.y)
                    if dist < FINGER_MIN_DIST and extended[i-1] == 1:
                        extended[i] = 0
                if i < 4:
                    tip_next = hand_landmarks[finger_tips[i+1]]
                    dist = np.hypot(tip_i.x - tip_next.x, tip_i.y - tip_next.y)
                    if dist < FINGER_MIN_DIST and extended[i+1] == 1:
                        extended[i+1] = 0

        total = sum(extended)
        if total == 0:
            return "拳头"
        elif total == 1:
            if extended[0] == 1:
                return "拇指"
            elif extended[1] == 1:
                return "食指"
            elif extended[2] == 1:
                return "中指"
            elif extended[3] == 1:
                return "无名指"
            else:
                return "小指"
        else:
            return str(total)

    # ---- 绘制单只手 ----
    def draw_hand_landmarks(self, frame, hand_landmarks, gesture):
        h, w, _ = frame.shape
        for lm in hand_landmarks:
            cx, cy = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (cx, cy), 5, (255, 0, 0), -1)

        finger_connections = [
            (1,2), (2,3), (3,4),
            (5,6), (6,7), (7,8),
            (9,10), (10,11), (11,12),
            (13,14), (14,15), (15,16),
            (17,18), (18,19), (19,20)
        ]
        palm_connections = [
            (0,1), (0,5), (0,17), (5,9), (9,13), (13,17)
        ]
        all_connections = finger_connections + palm_connections
        for i, j in all_connections:
            if i < len(hand_landmarks) and j < len(hand_landmarks):
                p1 = hand_landmarks[i]
                p2 = hand_landmarks[j]
                cv2.line(frame, (int(p1.x*w), int(p1.y*h)),
                         (int(p2.x*w), int(p2.y*h)), (255, 200, 0), 2)

        wrist = hand_landmarks[0]
        cx = int(wrist.x * w)
        cy = int(wrist.y * h) - 30
        cv2.putText(frame, gesture, (cx - 20, cy),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    # ---- 绘制左上角信息 ----
    def draw_info(self, frame, hand_gestures, obj_count):
        gesture_text = ", ".join(hand_gestures) if hand_gestures else "未检测到手"
        cv2.putText(frame, f"手势: {gesture_text}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
        cv2.putText(frame, f"FPS: {self.display_fps:.1f}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,0), 2)
        cv2.putText(frame, f"物品数: {obj_count}", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,0,255), 2)
        cv2.putText(frame, f"CPU (间隔{DETECT_INTERVAL}帧)", (10, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,255), 2)
        cv2.putText(frame, "按 'q' 退出", (10, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

    # ---- 人体骨架 ----
    def draw_pose_landmarks(self, frame, landmarks):
        h, w, _ = frame.shape
        key_points = [11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
        for i in key_points:
            if i < len(landmarks):
                lm = landmarks[i]
                cx, cy = int(lm.x * w), int(lm.y * h)
                cv2.circle(frame, (cx, cy), 3, (0, 255, 0), -1)
        connections = [
            (11,12), (11,13), (13,15), (12,14), (14,16),
            (11,23), (12,24), (23,24),
            (23,25), (25,27), (24,26), (26,28)
        ]
        for (i, j) in connections:
            if i < len(landmarks) and j < len(landmarks):
                p1 = landmarks[i]
                p2 = landmarks[j]
                cv2.line(frame, (int(p1.x*w), int(p1.y*h)),
                         (int(p2.x*w), int(p2.y*h)), (0,0,255), 2)

    # ---- 头部遮挡 ----
    def draw_face_mask(self, frame, landmarks):
        if not landmarks:
            return
        h, w, _ = frame.shape
        nose = landmarks[self.LANDMARKS['nose']]
        left_shoulder = landmarks[self.LANDMARKS['left_shoulder']]
        right_shoulder = landmarks[self.LANDMARKS['right_shoulder']]

        shoulder_pix = abs(left_shoulder.x - right_shoulder.x) * w
        if shoulder_pix < 10:
            shoulder_pix = w * 0.4

        base_h = shoulder_pix * 0.32
        left_radius = base_h * 1.05
        right_radius = base_h * 0.95
        up_radius = shoulder_pix * 0.32
        down_radius = shoulder_pix * 0.25

        left_radius = min(left_radius, w * 0.35)
        right_radius = min(right_radius, w * 0.35)
        up_radius = min(up_radius, h * 0.35)
        down_radius = min(down_radius, h * 0.30)

        nose_x = int(nose.x * w)
        nose_y = int(nose.y * h)
        center_x = nose_x
        center_y = nose_y

        grid_n = 12
        total_width = left_radius + right_radius
        total_height = up_radius + down_radius
        cell_w = total_width / grid_n
        cell_h = total_height / grid_n

        for i in range(grid_n):
            for j in range(grid_n):
                cx_cell = center_x - left_radius + (j + 0.5) * cell_w
                cy_cell = center_y - up_radius + (i + 0.5) * cell_h
                dx = cx_cell - center_x
                dy = cy_cell - center_y
                if dx < 0:
                    rx = left_radius
                else:
                    rx = right_radius
                if dy < 0:
                    ry = up_radius
                else:
                    ry = down_radius
                if (dx/rx)**2 + (dy/ry)**2 <= 1.0:
                    scale = random.uniform(1.0, 1.4)
                    draw_w = cell_w * scale
                    draw_h = cell_h * scale
                    x1 = int(cx_cell - draw_w / 2)
                    y1 = int(cy_cell - draw_h / 2)
                    x2 = int(cx_cell + draw_w / 2)
                    y2 = int(cy_cell + draw_h / 2)
                    x1 = max(0, x1)
                    y1 = max(0, y1)
                    x2 = min(w, x2)
                    y2 = min(h, y2)
                    if x2 > x1 and y2 > y1:
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 0), -1)

    # ---- YOLO 物品检测 ----
    def detect_objects(self, frame):
        results = self.yolo(frame, imgsz=self.yolo_imgsz, verbose=False)
        detected = []
        h, w = frame.shape[:2]
        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                label = self.yolo.names[cls]
                if label not in self.allowed_items:
                    continue
                if label == 'cup':
                    if conf < self.cup_conf_threshold:
                        continue
                elif label == 'cell phone':
                    if conf < self.phone_conf_threshold:
                        continue
                    width = x2 - x1
                    height = y2 - y1
                    aspect_ratio = width / height if height > 0 else 0
                    if aspect_ratio < 0.35 or aspect_ratio > 0.75:
                        continue
                    area = width * height
                    if area < 0.01 * w * h or area > 0.20 * w * h:
                        continue
                else:
                    if conf < self.conf_threshold:
                        continue
                detected.append((label, conf, (x1, y1, x2, y2)))
        if detected:
            print(f"[物品] {len(detected)}个: {[d[0] for d in detected]}")
        return detected

    def draw_detections(self, frame, detections):
        color_map = {
            'cup': (0, 255, 255), 'bottle': (255, 0, 255),
            'cell phone': (0, 255, 0), 'book': (255, 255, 0),
            'remote': (255, 128, 0), 'keyboard': (128, 255, 128),
            'mouse': (128, 128, 255), 'laptop': (255, 128, 255),
            'tv': (0, 128, 255), 'scissors': (255, 0, 0),
            'knife': (0, 0, 255), 'fork': (128, 0, 255),
            'spoon': (128, 255, 0)
        }
        for label, conf, (x1, y1, x2, y2) in detections:
            color = color_map.get(label, (255, 255, 255))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, label, (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    # ---- 主循环 ----
    def run(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("无法打开摄像头")
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        print("启动完成，按 'q' 退出")

        cv2.namedWindow('人体动作识别 (CPU优化)', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('人体动作识别 (CPU优化)', 800, 600)

        timestamp_ms = 0
        self.frame_counter = 0
        self.hands_frame_counter = 0
        self.fps_counter = 0
        self.fps_start_time = time.time()

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = Image(image_format=ImageFormat.SRGB, data=rgb_frame)

            # 姿态
            pose_result = self.pose_detector.detect_for_video(mp_image, timestamp_ms)
            if pose_result.pose_landmarks:
                pose_landmarks = pose_result.pose_landmarks[0]
                self.draw_pose_landmarks(frame, pose_landmarks)
                self.draw_face_mask(frame, pose_landmarks)

            # 手部
            self.hands_frame_counter += 1
            if self.hands_frame_counter % self.hands_interval == 0:
                hand_result = self.hand_detector.detect_for_video(mp_image, timestamp_ms)
                if hand_result.hand_landmarks:
                    self.cached_hands = []
                    for hand_lms in hand_result.hand_landmarks:
                        gesture = self.get_hand_gesture(hand_lms)
                        self.cached_hands.append((hand_lms, gesture))
                else:
                    self.cached_hands = []

            # 绘制每只手
            hand_gestures = []
            for hand_lms, gesture in self.cached_hands:
                self.draw_hand_landmarks(frame, hand_lms, gesture)
                hand_gestures.append(gesture)

            # 物品
            self.frame_counter += 1
            if self.frame_counter % self.detect_interval == 0:
                self.cached_detections = self.detect_objects(frame)
            if self.cached_detections:
                self.draw_detections(frame, self.cached_detections)

            # FPS
            self.fps_counter += 1
            current_time = time.time()
            elapsed = current_time - self.fps_start_time
            if elapsed >= self.fps_update_interval:
                self.display_fps = self.fps_counter / elapsed
                self.fps_counter = 0
                self.fps_start_time = current_time

            # 信息
            self.draw_info(frame, hand_gestures, len(self.cached_detections))

            cv2.imshow('人体动作识别 (CPU优化)', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            timestamp_ms += 33

        cap.release()
        cv2.destroyAllWindows()
        self.pose_detector.close()
        self.hand_detector.close()
        print("程序退出")

def main():
    recognizer = HumanActionRecognizer()
    recognizer.run()

if __name__ == "__main__":
    main()
