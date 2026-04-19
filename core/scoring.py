"""
评分模块，
根据偏差值进行评分和等级评定
"""
import numpy as np


def deviation_grade(d: float) -> str:
    """
    根据偏差值评定等级

    Args:
        d: 角度偏差值（度）

    Returns:
        等级字符串: "excellent", "good", "warning", "poor"
    """
    if d <= 5:
        return "excellent"
    elif d <= 15:
        return "good"
    elif d <= 30:
        return "warning"
    else:
        return "poor"


def score_from_dev(d: float) -> float:
    """
    根据偏差值计算评分（0-100）
    使用指数衰减函数，偏差越小评分越高
    Args:
        d: 角度偏差值（度）

    Returns:
        评分值（0-100）
    """
    return float(100 * np.exp(-d / 25))
