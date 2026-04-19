"""
单侧处理线程模块
包含 SideProcessor 类，用于在后台线程中处理单侧的输入源
"""
import time
import threading
from typing import TYPE_CHECKING

import cv2
import numpy as np

import mediapipe as mp
from mediapipe.tasks import python as _mp_tasks
from mediapipe.tasks.python import vision as _mp_vision

from config.model_config import MODEL_PATH
from core.geometry import extract_mp_angles
from core.symmetry import analyze_symmetry
from pose.rendering import draw_skeleton

# 避免循环导入
if TYPE_CHECKING:
    from .side_state import SideState


class SideProcessor(threading.Thread):
    """
    单侧处理线程类

    在后台线程中处理摄像头、视频或 C3D 文件输入，
    进行姿态检测并更新状态。
    """

    def __init__(self, side: "SideState", lock: threading.Lock):
        """
        初始化处理线程。

        Args:
            side: 单侧状态对象
            lock: 全局状态锁
        """
        super().__init__(daemon=True)
        self.side = side
        self.lock = lock
        self._stop = threading.Event()

    def stop(self):
        """停止处理线程"""
        self._stop.set()

    def run(self):
        """线程主运行方法"""
        if self.side.source == "c3d":
            self._run_c3d()
        else:
            self._run_video()

    def _run_c3d(self):
        """处理 C3D 文件源"""
        s = self.side
        loader = s.c3d_loader
        if not loader:
            self._finish()
            return

        interval = 1 / 30.0
        f = 0
        total = loader.n_frames

        while not self._stop.is_set():
            t0 = time.time()
            angles = loader.angles_to_mp_format(f)
            sym = analyze_symmetry(angles)
            frame = loader.render_frame(f, 480, 360, s.c3d_name[:20] or "C3D")

            with self.lock:
                s.angles = angles
                s.symmetry = sym
                s.latest_frame = frame
                s.detected = bool(angles)
                s.fps = 30.0
                s.c3d_frame = f

            # 按约 10fps 采样历史（每 3 帧记录一次）
            s._hist_counter += 1
            if angles and s._hist_counter % 3 == 0:
                norm_ang = angles if not isinstance(list(angles.values())[0], dict) \
                    else {k: v["angle"] for k, v in angles.items()}
                entry = {"t": round(time.time(), 3), "angles": norm_ang, "lm": []}

                # 渲染 C3D 帧缩略图，供时间轴回放使用
                c3d_thumb = loader.render_frame(f, 320, 240, s.c3d_name[:16] or "C3D")
                ok2, buf2 = cv2.imencode(".jpg", c3d_thumb, [cv2.IMWRITE_JPEG_QUALITY, 65])
                frame_bytes = buf2.tobytes() if ok2 else b""

                with s.history_lock:
                    s.history.append(entry)
                    s.frame_buffer.append(frame_bytes)

            f += 1
            if f >= total:
                # 所有帧分析完毕，自动停止
                break
            elapsed = time.time() - t0
            time.sleep(max(0, interval - elapsed))

        self._finish()

    def _run_video(self):
        """处理摄像头或视频文件源"""
        s = self.side
        source = s.camera_idx if s.source == "camera" else s.video_path
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            self._finish()
            return

        W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # 从文件读取原始帧率，摄像头或未知时回退到 30
        native_fps = cap.get(cv2.CAP_PROP_FPS)
        if native_fps <= 0 or native_fps > 240:
            native_fps = 30.0
        is_video = s.source == "video"
        frame_interval = 1.0 / native_fps if is_video else 0.0

        prev_t = time.time()
        display_fps = 0.0

        # ts_ms：严格递增的毫秒计数器，供 MediaPipe VIDEO 模式使用
        ts_ms = 0
        total_frame_idx = 0

        # 基于时间的采样：每 HIST_INTERVAL 秒的视频时间记录一条历史
        HIST_INTERVAL = 0.10   # 历史采样间隔，约 10fps
        _last_hist_video_t = -999.0   # 上一次写入历史记录时的视频时间

        opts = _mp_vision.PoseLandmarkerOptions(
            base_options=_mp_tasks.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=_mp_vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.55,
            min_pose_presence_confidence=0.55,
            min_tracking_confidence=0.55,
        )

        with _mp_vision.PoseLandmarker.create_from_options(opts) as det:
            while not self._stop.is_set():
                t_frame_start = time.time()
                ret, frame = cap.read()
                if not ret:
                    if is_video:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ts_ms = 0
                        _last_hist_video_t = -999.0
                        continue
                    break

                # 时间戳处理
                ts_ms += max(1, int(1000.0 / native_fps))
                if is_video:
                    pos_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                    if pos_msec > 0:
                        video_t_sec = pos_msec / 1000.0
                    else:
                        video_t_sec = total_frame_idx / native_fps
                else:
                    video_t_sec = time.time()
                total_frame_idx += 1

                # Pose detection
                now = time.time()
                display_fps = 0.9 * display_fps + 0.1 / (max(now - prev_t, 1e-9))
                prev_t = now
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                res = det.detect_for_video(mp_img, ts_ms)
                angles = {}
                sym = {}
                detected = False

                if res.pose_landmarks:
                    detected = True
                    angles = extract_mp_angles(res.pose_landmarks[0], W, H)
                    sym = analyze_symmetry(angles)

                # History recording (time-based, 10 fps)
                if detected and angles and (video_t_sec - _last_hist_video_t) >= HIST_INTERVAL:
                    _last_hist_video_t = video_t_sec
                    lm_flat = []
                    if res.pose_landmarks:
                        for pt in res.pose_landmarks[0]:
                            lm_flat += [round(pt.x, 4), round(pt.y, 4)]
                    entry = {
                        "t": round(video_t_sec, 3),
                        "angles": {k: v["angle"] for k, v in angles.items()},
                        "lm": lm_flat,
                    }
                    clean = cv2.resize(frame, (320, 240))
                    ok2, buf2 = cv2.imencode(".jpg", clean, [cv2.IMWRITE_JPEG_QUALITY, 72])
                    frame_bytes = buf2.tobytes() if ok2 else b""
                    with s.history_lock:
                        s.history.append(entry)
                        s.frame_buffer.append(frame_bytes)

                # Draw skeleton on live feed
                if res.pose_landmarks:
                    draw_skeleton(frame, res.pose_landmarks[0], angles, None, W, H)
                label_fps = display_fps if not is_video else native_fps
                cv2.putText(
                    frame,
                    f"{'Video' if is_video else 'FPS'} {label_fps:.0f}  {s.label}",
                    (8, 22),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (80, 180, 80),
                    1,
                    cv2.LINE_AA
                )

                with self.lock:
                    s.angles = angles
                    s.symmetry = sym
                    s.latest_frame = frame.copy()
                    s.detected = detected
                    s.fps = display_fps

                # Throttle to real-time for video files
                if is_video:
                    elapsed = time.time() - t_frame_start
                    sleep_t = frame_interval - elapsed
                    if sleep_t > 0:
                        time.sleep(sleep_t)

        cap.release()
        self._finish()

    def _finish(self):
        """处理结束时的清理工作"""
        from pose.rendering import make_placeholder
        with self.lock:
            self.side.running = False
            self.side.latest_frame = make_placeholder(
                text=f"侧 {self.side.label} — 已停止",
                side=self.side.label
            )
