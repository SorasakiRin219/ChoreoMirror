"""
时序分析模块

包含数据预处理、DTW 算法、对齐算法和时序对比函数。
"""

from .preprocessing import (
    fill_nan,
    resample,
)
from .dtw import (
    dtw_path,
    best_start,
)
from .alignment import (
    best_align_joint,
    composite_global_align,
    segment_diff,
)
from .timeseries import (
    compare_timeseries,
)

__all__ = [
    # preprocessing
    "fill_nan",
    "resample",
    # dtw
    "dtw_path",
    "best_start",
    # alignment
    "best_align_joint",
    "composite_global_align",
    "segment_diff",
    # timeseries
    "compare_timeseries",
]
