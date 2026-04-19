"""
配置模块，
包含应用中的常量定义和模型配置
"""

from .constants import (
    POSE_CONNECTIONS,
    MP_JOINT_DEF,
    DEFAULT_C3D_MAP,
    PRESET_MAPS,
    BODY_REGIONS,
    REGION_CN,
)
from .model_config import (
    MODEL_PATH,
    MODEL_URL,
    ensure_model,
)

__all__ = [
    # constants
    "POSE_CONNECTIONS",
    "MP_JOINT_DEF",
    "DEFAULT_C3D_MAP",
    "PRESET_MAPS",
    "BODY_REGIONS",
    "REGION_CN",
    # model_config
    "MODEL_PATH",
    "MODEL_URL",
    "ensure_model",
]
