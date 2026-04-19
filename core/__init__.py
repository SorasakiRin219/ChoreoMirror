"""
核心数学模块，
包含几何计算、对称性分析、对比分析和评分函数
"""

from .geometry import (
    calculate_angle,
    extract_mp_angles,
)
from .symmetry import (
    analyze_symmetry,
)
from .comparison import (
    compare_sides,
)
from .scoring import (
    deviation_grade,
    score_from_dev,
)

__all__ = [
    # geometry
    "calculate_angle",
    "extract_mp_angles",
    # symmetry
    "analyze_symmetry",
    # comparison
    "compare_sides",
    # scoring
    "deviation_grade",
    "score_from_dev",
]
