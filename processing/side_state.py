"""
单侧状态模块

包含 SideState 类，用于管理单侧的运行状态和数据。
"""
from typing import Dict, Optional
from collections import deque
import threading
import numpy as np

from data.c3d_loader import C3DLoader
from pose.rendering import make_placeholder


class SideState:
    """
    单侧状态管理类。

    管理单个侧（A 或 B）的所有状态信息，包括输入源、
    角度数据、对称性分析、历史记录等。
    """

    def __init__(self, label: str):
        """
        初始化单侧状态。

        Args:
            label: 侧标识（"A" 或 "B"）
        """
        self.label = label           # "A" or "B"
        self.source = "camera"      # 输入源类型：摄像头/视频/C3D
        self.camera_idx = 0
        self.video_path: Optional[str] = None
        self.c3d_loader: Optional[C3DLoader] = None
        self.c3d_name = ""
        self.c3d_frame = 0         # 当前播放帧索引
        self.angles: Dict = {}
        self.symmetry: Dict = {}
        self.latest_frame: np.ndarray = make_placeholder(
            text=f"侧 {label} — 等待开始",
            side=label
        )
        self.running = False
        self.detected = False
        self.fps = 0.0
        self.data_loaded = False     # 历史数据是否已装载（独立于 running）

        # 时序历史记录: {"t": 秒, "angles": {关节名:角度}, "lm": [x0,y0,x1,y1,...]}
        self.history: deque = deque(maxlen=1800)
        self.frame_buffer: deque = deque(maxlen=1800)
        self.history_lock = threading.Lock()
        self._hist_counter = 0

    def to_dict(self) -> Dict:
        """
        将状态转换为字典格式。

        Returns:
            包含所有状态信息的字典
        """
        return {
            "label": self.label,
            "source": self.source,
            "running": self.running,
            "data_loaded": self.data_loaded,
            "n_frames": len(self.history),
            "detected": self.detected,
            "fps": round(self.fps, 1),
            "angles": self.angles,
            "symmetry": self.symmetry,
            "c3d_loaded": self.c3d_loader is not None,
            "c3d_name": self.c3d_name,
            "c3d_frame": self.c3d_frame,
            "c3d_total": self.c3d_loader.n_frames if self.c3d_loader else 0,
        }
