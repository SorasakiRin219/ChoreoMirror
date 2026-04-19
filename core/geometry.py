"""
几何计算模块，
包含角度计算和 MediaPipe 姿态角度提取函数
"""
from typing import Dict
import numpy as np

from config.constants import MP_JOINT_DEF


def calculate_angle(a, b, c) -> float:
    """
    计算三个点组成的角度（以度为单位）

    Args:
        a: 第一个点的坐标
        b: 顶点的坐标（角度的中心）
        c: 第三个点的坐标

    Returns:
        角度值（0-180度），如果点重合则返回 0
    """
    ba, bc = np.asarray(a) - np.asarray(b), np.asarray(c) - np.asarray(b)
    n = np.linalg.norm(ba) * np.linalg.norm(bc)
    if n <= 1e-9:
        return 0.0
    return float(np.degrees(np.arccos(np.clip(np.dot(ba, bc) / n, -1, 1))))


def extract_mp_angles(landmarks, w: int, h: int) -> Dict:
    """
    从 MediaPipe 关键点中提取各关节角度

    Args:
        landmarks: MediaPipe pose landmarks 列表
        w: 图像宽度
        h: 图像高度

    Returns:
        包含各关节角度的字典，格式为：
        {
            "joint_name": {
                "angle": float,
                "cn_name": str,
                "visibility": float
            },
            ...
        }
    """
    lm = landmarks
    out = {}

    for key, (ai, bi, ci, cn) in MP_JOINT_DEF.items():
        try:
            # 计算三个点的最小可见度
            vis = min(lm[ai].visibility or 0, lm[bi].visibility or 0, lm[ci].visibility or 0)
            if vis < 0.45:
                continue

            # 将归一化坐标转换为像素坐标
            def pt(i, _l=lm):
                return np.array([_l[i].x * w, _l[i].y * h])

            # 计算角度
            angle = calculate_angle(pt(ai), pt(bi), pt(ci))

            out[key] = {
                "angle": round(angle, 1),
                "cn_name": cn,
                "visibility": round(vis, 2)
            }
        except Exception:
            pass

    return out
