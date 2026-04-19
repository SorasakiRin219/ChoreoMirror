"""
姿态检测模块,
MediaPipe 姿态检测器封装和骨架绘制函数
"""

from .rendering import (
    draw_skeleton,
    make_placeholder,
)

__all__ = [
    "draw_skeleton",
    "make_placeholder",
]
