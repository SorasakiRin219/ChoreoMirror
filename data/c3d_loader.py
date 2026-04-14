"""
C3D 文件加载器

用于加载和解析 C3D 运动捕捉文件格式。
"""
from typing import Dict, List
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

from config.constants import MP_JOINT_DEF, DEFAULT_C3D_MAP
from core.geometry import calculate_angle


class C3DLoader:
    """
    C3D 运动捕捉文件加载器。

    支持解析 C3D 文件并提取关节角度序列。
    """

    def __init__(self, path: str, marker_map: Dict = None):
        """
        初始化 C3D 加载器。

        Args:
            path: C3D 文件路径
            marker_map: 标记点映射字典，默认使用 DEFAULT_C3D_MAP
        """
        self.path = path
        self.marker_map = marker_map or DEFAULT_C3D_MAP
        self.fps = 100.0
        self.n_frames = 0
        self.angle_seq: Dict[str, np.ndarray] = {}
        self.mean_angles: Dict[str, float] = {}
        self._marker_data: Dict[str, np.ndarray] = {}
        self._marker_xyz_raw: Dict[str, np.ndarray] = {}
        self.loaded_joints: List[str] = []
        self.missing_joints: List[str] = []
        self.available_markers: List[str] = []
        self._load()

    def _load(self):
        """加载 C3D 文件并计算关节角度序列"""
        import ezc3d

        c3d = ezc3d.c3d(self.path)
        self.fps = float(c3d["header"]["points"]["frame_rate"])
        labels = [l.strip() for l in c3d["parameters"]["POINT"]["LABELS"]["value"]]
        data = c3d["data"]["points"]
        self.n_frames = data.shape[2]
        self.available_markers = labels

        # 加载标记点数据
        for i, label in enumerate(labels):
            xyz = data[:3, i, :].T.copy()
            xyz[np.all(np.abs(xyz) < 1e-6, axis=1)] = np.nan
            self._marker_data[label] = xyz

        available = set(labels)

        # 计算各关节角度序列
        for jk, jdef in self.marker_map.items():
            resolved = []
            for m in jdef["markers"]:
                # 尝试匹配标记点（不区分大小写）
                r = m if m in available else next((a for a in available if a.upper() == m.upper()), None)
                resolved.append(r)

            # 如果有关键标记点缺失，跳过该关节
            if any(r is None for r in resolved):
                self.missing_joints.append(jk)
                continue

            seq = np.full(self.n_frames, np.nan)
            for f in range(self.n_frames):
                pts = [self._marker_data[r][f] for r in resolved]
                if any(np.any(np.isnan(p)) for p in pts):
                    continue
                seq[f] = calculate_angle(pts[0], pts[1], pts[2])

            # 如果有效数据不足，跳过该关节
            if len(seq[~np.isnan(seq)]) < 5:
                self.missing_joints.append(jk)
                continue

            self.angle_seq[jk] = seq
            self.mean_angles[jk] = float(np.nanmean(seq))
            self.loaded_joints.append(jk)

    def get_frame_angles(self, f: int) -> Dict[str, float]:
        """
        获取指定帧的所有关节角度。

        Args:
            f: 帧索引

        Returns:
            关节名称到角度值的字典
        """
        f = max(0, min(f, self.n_frames - 1))
        return {k: float(v[f]) for k, v in self.angle_seq.items() if not np.isnan(v[f])}

    def get_mean_angles(self) -> Dict[str, float]:
        """
        获取所有关节的平均角度。

        Returns:
            关节名称到平均角度值的字典
        """
        return dict(self.mean_angles)

    def render_frame(self, f: int, w: int = 480, h: int = 360, label: str = "C3D") -> np.ndarray:
        """
        将 C3D 3D 标记点数据渲染为棒状人体角度条形图。
        使用与整体 UI 风格一致的配色方案。

        Args:
            f: 帧索引
            w: 图像宽度
            h: 图像高度
            label: 标签文本

        Returns:
            渲染后的图像
        """
        # UI 配色方案（与 style.css 保持一致）
        BG_DEEP = (32, 17, 11)           # #0B1120 - 深海军蓝背景
        BAR_BG = (59, 41, 30, 128)       # rgba(30, 41, 59, 0.5) - 条形图背景
        CYAN = (248, 189, 56)            # #38bdf8 - 青色主题
        PURPLE = (250, 139, 167)         # #a78bfa - 紫色主题
        TEXT_PRIMARY = (252, 250, 248)   # #f8fafc - 主要文本（白色）
        TEXT_SECONDARY = (184, 163, 148) # #94a3b8 - 次要文本（浅灰）
        TEXT_MUTED = (139, 116, 100)     # #64748b - 淡化文本（灰色）

        canvas = np.zeros((h, w, 3), np.uint8)
        canvas[:] = BG_DEEP

        angles = self.get_frame_angles(f)

        # 绘制角度条形图
        bar_x = 16
        bar_y = 44
        bw = w - 32
        bh = 14
        gap = 22

        # 使用 OpenCV 绘制背景条形图（非文本部分）
        for i, (key, ang) in enumerate(angles.items()):
            y = bar_y + i * gap
            # 青紫渐变条形图
            t = i / max(len(angles) - 1, 1)
            color = (
                int(CYAN[0] + (PURPLE[0] - CYAN[0]) * t),
                int(CYAN[1] + (PURPLE[1] - CYAN[1]) * t),
                int(CYAN[2] + (PURPLE[2] - CYAN[2]) * t),
            )
            fill = max(1, int(ang / 180 * bw))
            cv2.rectangle(canvas, (bar_x, y), (bar_x + bw, y + bh), (59, 41, 30), -1)
            cv2.rectangle(canvas, (bar_x, y), (bar_x + fill, y + bh), color, -1)

        # 转换为 PIL 图像以绘制中文文本
        pil_img = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil_img)

        # 字体加载策略（跨平台兼容）
        font = None
        font_small = None
        font_paths = [
            # Windows 系统字体
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simsun.ttc",
            # macOS 系统字体
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            # Linux 系统字体
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]

        for fp in font_paths:
            try:
                font = ImageFont.truetype(fp, 16)
                font_small = ImageFont.truetype(fp, 13)
                break
            except:
                continue

        if font is None:
            font = ImageFont.load_default()
            font_small = font

        # 绘制顶部标签（使用青色主题色）
        label_text = f"{label}  Frame {f}/{self.n_frames-1}"
        draw.text((8, 6), label_text, font=font, fill=CYAN[::-1])  # BGR -> RGB

        # 绘制关节名称和角度（使用次要文本颜色）
        for i, (key, ang) in enumerate(angles.items()):
            y = bar_y + i * gap
            cn = MP_JOINT_DEF.get(key, ("", "", "", key))[3]
            text = f"{cn}: {ang:.0f}°"
            draw.text((bar_x + 4, y + 1), text, font=font_small, fill=TEXT_PRIMARY[::-1])

        # 绘制底部时间戳（使用淡化文本颜色）
        ts = f"{f / self.fps:.1f}s"
        draw.text((w - 50, h - 20), ts, font=font_small, fill=TEXT_MUTED[::-1])

        # 转换回 OpenCV 格式
        canvas = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        return canvas

    def angles_to_mp_format(self, f: int) -> Dict:
        """
        将角度数据转换为 MediaPipe 格式。

        Args:
            f: 帧索引

        Returns:
            MediaPipe 格式的角度字典
        """
        raw = self.get_frame_angles(f)
        return {
            k: {"angle": v, "cn_name": MP_JOINT_DEF[k][3], "visibility": 1.0}
            for k, v in raw.items() if k in MP_JOINT_DEF
        }
