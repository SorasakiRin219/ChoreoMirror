"""
对比分析模块

对比分析两组关节角度的差异。
"""
from typing import Dict
import numpy as np

from .scoring import score_from_dev, deviation_grade


def compare_sides(a_angles: Dict, b_angles: Dict) -> Dict:
    """
    逐关节比较 A（学生）与 B（参考）的单帧角度差异。

    Args:
        a_angles: A 侧关节角度字典
        b_angles: B 侧关节角度字典

    Returns:
        包含各关节偏差和综合评分的字典：
        {
            "joints": {
                "joint_name": {
                    "current": float,
                    "standard": float,
                    "deviation": float,
                    "grade": str,
                    "score": float,
                    "cn_name": str,
                    "direction": str
                },
                ...
            },
            "overall_score": float
        }
    """
    joints = []
    scores = []

    for key, info in a_angles.items():
        if key not in b_angles:
            continue

        # 处理不同格式的角度值
        if isinstance(b_angles[key], dict):
            ref_angle = b_angles[key]["angle"]
        else:
            ref_angle = b_angles[key]

        # 计算偏差
        deviation = abs(info["angle"] - ref_angle)
        score = score_from_dev(deviation)

        joints.append((
            key,
            {
                "current": info["angle"],
                "standard": round(ref_angle, 1),
                "deviation": round(deviation, 1),
                "grade": deviation_grade(deviation),
                "score": round(score, 1),
                "cn_name": info["cn_name"],
                "direction": "偏大" if info["angle"] > ref_angle else "偏小",
            }
        ))

        scores.append(score)

    return {
        "joints": dict(joints),
        "overall_score": round(float(np.mean(scores)), 1) if scores else 0.0
    }
