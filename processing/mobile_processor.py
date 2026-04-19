"""
移动端摄像头单帧处理模块（待优化）（移动端推流实际上现在用不了）
处理从前端 WebRTC 推流过来的单帧图像，进行姿态检测并更新状态
"""
import time
import threading
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as _mp_tasks
from mediapipe.tasks.python import vision as _mp_vision

from config.model_config import MODEL_PATH
from core.geometry import extract_mp_angles
from core.symmetry import analyze_symmetry
from pose.rendering import draw_skeleton

# 按线程缓存 detector，避免每次请求重新创建
_detectors: dict = {}
_ts_ms_counters: dict = {"a": [0], "b": [0]}


def _get_detector():
    """获取当前线程的 PoseLandmarker 实例（缓存）。"""
    tid = threading.current_thread().ident
    if tid not in _detectors:
        opts = _mp_vision.PoseLandmarkerOptions(
            base_options=_mp_tasks.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=_mp_vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.55,
            min_pose_presence_confidence=0.55,
            min_tracking_confidence=0.55,
        )
        _detectors[tid] = _mp_vision.PoseLandmarker.create_from_options(opts)
    return _detectors[tid]


def process_mobile_frame(side, frame_bgr: np.ndarray, global_lock, which: str):
    """
    处理移动端传来的单帧图像并更新 side 状态

    Args:
        side: SideState 实例
        frame_bgr: BGR 格式的 numpy 图像
        global_lock: AppState 全局锁
        which: 'a' 或 'b'
    """
    H, W = frame_bgr.shape[:2]

    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    ts_ms = _ts_ms_counters[which][0]
    _ts_ms_counters[which][0] += 33  # 约 30fps 递增

    det = _get_detector()
    res = det.detect_for_video(mp_img, ts_ms)

    angles = {}
    sym = {}
    detected = False

    if res.pose_landmarks:
        detected = True
        angles = extract_mp_angles(res.pose_landmarks[0], W, H)
        sym = analyze_symmetry(angles)
        draw_skeleton(frame_bgr, res.pose_landmarks[0], angles, None, W, H)

    # 叠加简洁的移动端 FPS/状态标签
    label = f"Mobile {which.upper()}  {side.fps:.0f}fps"
    cv2.putText(
        frame_bgr, label, (8, 22),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 180, 80), 1, cv2.LINE_AA
    )

    now = time.time()

    # 历史记录采样（约 10fps）
    should_record = False
    if detected and angles:
        last_t = getattr(side, "_mobile_last_hist_t", 0)
        if now - last_t >= 0.10:
            should_record = True
            side._mobile_last_hist_t = now

    if should_record:
        lm_flat = []
        for pt in res.pose_landmarks[0]:
            lm_flat += [round(pt.x, 4), round(pt.y, 4)]
        entry = {
            "t": round(now, 3),
            "angles": {k: v["angle"] for k, v in angles.items()},
            "lm": lm_flat,
        }
        thumb = cv2.resize(frame_bgr, (320, 240))
        ok2, buf2 = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 72])
        frame_bytes = buf2.tobytes() if ok2 else b""

        with side.history_lock:
            side.history.append(entry)
            side.frame_buffer.append(frame_bytes)
        side._hist_counter += 1

    with global_lock:
        side.angles = angles
        side.symmetry = sym
        side.latest_frame = frame_bgr.copy()
        side.detected = detected
        side.fps = 15.0  # 移动端推帧简化为固定参考值
