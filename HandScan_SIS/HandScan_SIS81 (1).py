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

# ===================== 调优参数（全部震撼化） =====================
YOLO_IMGSZ = 224
DETECT_INTERVAL = 10
CONF_THRESHOLD = 0.45
CUP_CONF_THRESHOLD = 0.30
PHONE_CONF_THRESHOLD = 0.65
USE_LITE_POSE = True
HANDS_DETECT_INTERVAL = 2
FPS_UPDATE_INTERVAL = 0.25

# ---- 手部判定阈值 ----
FINGER_Y_THRESHOLD = 0.035
NON_INDEX_Y_THRESHOLD = 0.055       # 中、无名、小指阈值较高
THUMB_DIST_THRESHOLD = 0.08
THUMB_X_THRESHOLD = 0.03
THUMB_Z_THRESHOLD = 0.02
FINGER_MIN_DIST = 0.03
THUMB_INDEX_DIST_THRESHOLD = 0.06
THUMB_MCP_PALM_DIST_THRESHOLD = 0.055
THUMB_TIP_PALM_DIST_THRESHOLD = 0.075

# ---- 烟花参数（增强） ----
FIREWORK_DURATION = 4.0
PARTICLE_COUNT = 150
# 移除冷却参数，改为基于烟花播放状态

# ---- 喷泉参数（增强） ----
FOUNTAIN_PARTICLE_RATE = 40
FOUNTAIN_PARTICLE_LIFE = 2.5
FOUNTAIN_GRAVITY = 180
FOUNTAIN_SPEED_MIN = 120
FOUNTAIN_SPEED_MAX = 280
FOUNTAIN_SIZE_MIN = 6
FOUNTAIN_SIZE_MAX = 16
MAX_FOUNTAIN_PARTICLES = 500

# ---- 冲击波参数（增强） ----
SHOCKWAVE_PARTICLE_COUNT = 80
SHOCKWAVE_SPEED = 450
SHOCKWAVE_LIFE = 2.2
SHOCKWAVE_SIZE_START = 18
SHOCKWAVE_SIZE_END = 1
SHOCKWAVE_COOLDOWN = 2.0

# ---- 镜头抖动参数 ----
SHAKE_DURATION = 0.3
SHAKE_INTENSITY = 15
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

        # ---- 烟花状态 ----
        self.firework_active = False
        self.firework_start_time = 0.0
        self.particles = []
        self.firework_count = 0            # 烟花触发次数

        # ---- 喷泉状态 ----
        self.fountain_particles = []
        self.fountain_active = False

        # ---- 冲击波状态 ----
        self.shockwave_particles = []
        self.shockwave_active = False
        self.shockwave_trigger_time = 0.0

        # ---- 镜头抖动状态 ----
        self.shake_active = False
        self.shake_start_time = 0.0
        self.shake_duration = SHAKE_DURATION
        self.shake_intensity = SHAKE_INTENSITY

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

    # ---- 手势识别 ----
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
            if tip_id == 4:
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
                if tip_id == 8:  # 食指
                    thresh = FINGER_Y_THRESHOLD
                else:
                    thresh = NON_INDEX_Y_THRESHOLD
                if tip.y < pip.y - thresh:
                    extended.append(1)
                else:
                    extended.append(0)

        # ---- 拇指收起判定 ----
        if extended[0] == 1:
            thumb_mcp = hand_landmarks[2]
            thumb_tip = hand_landmarks[4]
            dist_mcp_palm = np.hypot(thumb_mcp.x - palm_center[0], thumb_mcp.y - palm_center[1])
            dist_tip_palm = np.hypot(thumb_tip.x - palm_center[0], thumb_tip.y - palm_center[1])
            if dist_mcp_palm < THUMB_MCP_PALM_DIST_THRESHOLD or dist_tip_palm < THUMB_TIP_PALM_DIST_THRESHOLD:
                extended[0] = 0

        # ---- 拇指-食指距离抑制 ----
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

    # ---- 镜头抖动 ----
    def start_shake(self):
        self.shake_active = True
        self.shake_start_time = time.time()

    def apply_shake(self, frame):
        if not self.shake_active:
            return frame
        elapsed = time.time() - self.shake_start_time
        if elapsed >= self.shake_duration:
            self.shake_active = False
            return frame
        dx = random.randint(-self.shake_intensity, self.shake_intensity)
        dy = random.randint(-self.shake_intensity, self.shake_intensity)
        if dx == 0 and dy == 0:
            return frame
        h, w = frame.shape[:2]
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        shaken = cv2.warpAffine(frame, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
        return shaken

    # ---- 烟花特效 ----
    def trigger_firework(self, center_x, center_y):
        self.firework_active = True
        self.firework_start_time = time.time()
        self.particles = []
        for _ in range(PARTICLE_COUNT):
            angle = random.uniform(0, 2 * np.pi)
            speed = random.uniform(150, 400)
            vx = speed * np.cos(angle)
            vy = speed * np.sin(angle)
            size = random.uniform(3, 10)
            b = random.randint(100, 200)
            g = random.randint(50, 150)
            r = random.randint(200, 255)
            color = (b, g, r)
            life = random.uniform(0.5, FIREWORK_DURATION)
            self.particles.append({
                'x': center_x,
                'y': center_y,
                'vx': vx,
                'vy': vy,
                'size': size,
                'color': color,
                'max_life': life,
                'life': life
            })

    def update_firework(self, dt):
        if not self.firework_active:
            return False
        elapsed = time.time() - self.firework_start_time
        if elapsed >= FIREWORK_DURATION:
            self.firework_active = False
            self.particles = []
            return False

        alive = False
        for p in self.particles:
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['vy'] += 150 * dt
            p['life'] -= dt
            if p['life'] > 0:
                alive = True
        if not alive:
            self.firework_active = False
            self.particles = []
            return False
        return True

    def draw_firework(self, frame):
        for p in self.particles:
            if p['life'] <= 0:
                continue
            ratio = p['life'] / p['max_life']
            size = p['size'] * (0.3 + 0.7 * ratio)
            bright = int(255 * ratio)
            color = (min(p['color'][0], bright), min(p['color'][1], bright), min(p['color'][2], bright))
            cv2.circle(frame, (int(p['x']), int(p['y'])), int(size), color, -1)

    # ---- 喷泉特效 ----
    def add_fountain_particle(self, tip_x, tip_y, dt, generate_new=True):
        if generate_new:
            if len(self.fountain_particles) < MAX_FOUNTAIN_PARTICLES:
                num_new = int(FOUNTAIN_PARTICLE_RATE * dt)
                for _ in range(num_new):
                    angle = random.uniform(-np.pi/2, np.pi/2)
                    speed = random.uniform(FOUNTAIN_SPEED_MIN, FOUNTAIN_SPEED_MAX)
                    vx = speed * np.sin(angle) * 0.8
                    vy = -speed * np.cos(angle)
                    vx += random.uniform(-20, 20)
                    size = random.uniform(FOUNTAIN_SIZE_MIN, FOUNTAIN_SIZE_MAX)
                    life = random.uniform(0.8, FOUNTAIN_PARTICLE_LIFE)
                    ratio = random.random()
                    b = int(50 + 200 * ratio)
                    g = int(255 * (1 - 0.8 * ratio))
                    r = int(255 * (0.5 + 0.5 * ratio))
                    color = (b, g, r)
                    self.fountain_particles.append({
                        'x': tip_x,
                        'y': tip_y,
                        'vx': vx,
                        'vy': vy,
                        'size': size,
                        'color': color,
                        'max_life': life,
                        'life': life
                    })

        for p in self.fountain_particles:
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['vy'] += FOUNTAIN_GRAVITY * dt
            p['life'] -= dt
            p['size'] *= (1 - 0.5 * dt / p['max_life'])

        self.fountain_particles = [p for p in self.fountain_particles if p['life'] > 0]

    def draw_fountain(self, frame):
        for p in self.fountain_particles:
            if p['life'] <= 0:
                continue
            ratio = p['life'] / p['max_life']
            size = max(2, int(p['size'] * (0.3 + 0.7 * ratio)))
            bright = int(255 * ratio)
            color = (min(p['color'][0], bright), min(p['color'][1], bright), min(p['color'][2], bright))
            x, y = int(p['x']), int(p['y'])
            cv2.rectangle(frame, (x - size//2, y - size//2), (x + size//2, y + size//2), color, -1)

    # ---- 冲击波特效 ----
    def trigger_shockwave(self, hand_positions):
        current_time = time.time()
        if self.shockwave_active:
            return
        if current_time - self.shockwave_trigger_time < SHOCKWAVE_COOLDOWN:
            return

        self.shockwave_active = True
        self.shockwave_trigger_time = current_time
        self.shockwave_particles = []
        self.start_shake()

        for (cx, cy) in hand_positions:
            for i in range(SHOCKWAVE_PARTICLE_COUNT):
                angle = random.uniform(0, 2 * np.pi)
                speed = SHOCKWAVE_SPEED * random.uniform(0.8, 1.2)
                vx = speed * np.cos(angle)
                vy = speed * np.sin(angle)
                size = random.uniform(SHOCKWAVE_SIZE_START * 0.6, SHOCKWAVE_SIZE_START * 1.4)
                b = random.randint(200, 255)
                g = random.randint(100, 200)
                r = random.randint(0, 80)
                color = (b, g, r)
                life = SHOCKWAVE_LIFE * random.uniform(0.8, 1.2)
                self.shockwave_particles.append({
                    'x': cx,
                    'y': cy,
                    'vx': vx,
                    'vy': vy,
                    'size': size,
                    'color': color,
                    'max_life': life,
                    'life': life
                })

    def update_shockwave(self, dt):
        if not self.shockwave_active:
            return False
        alive = False
        for p in self.shockwave_particles:
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['life'] -= dt
            ratio = p['life'] / p['max_life']
            p['size'] = SHOCKWAVE_SIZE_START * (0.3 + 0.7 * ratio)
            if p['life'] > 0:
                alive = True
        self.shockwave_particles = [p for p in self.shockwave_particles if p['life'] > 0]
        if not alive:
            self.shockwave_active = False
            self.shockwave_particles = []
            return False
        return True

    def draw_shockwave(self, frame):
        for p in self.shockwave_particles:
            if p['life'] <= 0:
                continue
            ratio = p['life'] / p['max_life']
            size = max(2, int(p['size'] * (0.3 + 0.7 * ratio)))
            bright = int(255 * ratio)
            color = (min(p['color'][0], bright), min(p['color'][1], bright), min(p['color'][2], bright))
            x, y = int(p['x']), int(p['y'])
            cv2.rectangle(frame, (x - size//2, y - size//2), (x + size//2, y + size//2), color, -1)

    # ---- 绘制手部 ----
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

    # ---- 绘制信息 ----
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
        dt = 0.033

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = Image(image_format=ImageFormat.SRGB, data=rgb_frame)

            # ---- 姿态 ----
            pose_result = self.pose_detector.detect_for_video(mp_image, timestamp_ms)
            if pose_result.pose_landmarks:
                pose_landmarks = pose_result.pose_landmarks[0]
                self.draw_pose_landmarks(frame, pose_landmarks)
                self.draw_face_mask(frame, pose_landmarks)

            # ---- 手部 ----
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

            hand_gestures = []
            index_found = False
            fist_positions = []
            for hand_lms, gesture in self.cached_hands:
                self.draw_hand_landmarks(frame, hand_lms, gesture)
                hand_gestures.append(gesture)
                if gesture == "食指":
                    h, w, _ = frame.shape
                    tip = hand_lms[8]
                    tip_x = int(tip.x * w)
                    tip_y = int(tip.y * h)
                    self.add_fountain_particle(tip_x, tip_y, dt, generate_new=True)
                    index_found = True
                elif gesture == "拳头":
                    h, w, _ = frame.shape
                    wrist = hand_lms[0]
                    wx = int(wrist.x * w)
                    wy = int(wrist.y * h)
                    fist_positions.append((wx, wy))

            if not index_found:
                self.add_fountain_particle(0, 0, dt, generate_new=False)

            if self.fountain_particles:
                self.draw_fountain(frame)

            # ---- 冲击波 ----
            if len(fist_positions) >= 2:
                self.trigger_shockwave(fist_positions[:2])

            if self.shockwave_active:
                if self.update_shockwave(dt):
                    self.draw_shockwave(frame)

            # ---- 烟花（基于播放状态，无冷却间隔） ----
            current_time = time.time()
            # 只有当烟花不在播放中时，才允许触发新烟花
            if not self.firework_active:
                for gesture in hand_gestures:
                    if gesture == "2":
                        h, w, _ = frame.shape
                        cx, cy = w // 2, h // 2
                        self.trigger_firework(cx, cy)
                        self.firework_count += 1
                        # 记录触发日志
                        print(f"[烟花] 第 {self.firework_count} 次触发，时间: {time.strftime('%H:%M:%S')}")
                        break  # 每帧只触发一次

            if self.firework_active:
                if self.update_firework(dt):
                    self.draw_firework(frame)

            # ---- 物品 ----
            self.frame_counter += 1
            if self.frame_counter % self.detect_interval == 0:
                self.cached_detections = self.detect_objects(frame)
            if self.cached_detections:
                self.draw_detections(frame, self.cached_detections)

            # ---- FPS ----
            if current_time - self.fps_start_time >= self.fps_update_interval:
                self.display_fps = self.fps_counter / (current_time - self.fps_start_time)
                self.fps_counter = 0
                self.fps_start_time = current_time
            self.fps_counter += 1
            dt = 1.0 / self.display_fps if self.display_fps > 0 else 0.033

            self.draw_info(frame, hand_gestures, len(self.cached_detections))

            # ---- 镜头抖动 ----
            frame = self.apply_shake(frame)

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