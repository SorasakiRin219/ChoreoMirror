"""
数据预处理模块

包含 NaN 填充和数组重采样函数。
"""
from typing import Optional
import numpy as np


def fill_nan(arr: np.ndarray) -> Optional[np.ndarray]:
    """
    线性插值填充内部 NaN，首尾向外填充。
    有效点不足 3 个时返回 None。

    Args:
        arr: 可能包含 NaN 的数组

    Returns:
        填充后的数组，或 None（如果有效点不足 3 个）
    """
    valid = ~np.isnan(arr)
    if valid.sum() < 3:
        return None

    out = arr.copy()
    idx = np.arange(len(arr))
    out[~valid] = np.interp(idx[~valid], idx[valid], arr[valid])
    return out


def resample(arr: np.ndarray, n: int) -> np.ndarray:
    """
    通过线性插值将数组重采样为精确 n 个点。

    Args:
        arr: 原始数组
        n: 目标点数

    Returns:
        重采样后的数组
    """
    if len(arr) == n:
        return arr
    return np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(arr)), arr)
