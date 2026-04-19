"""
常量定义模块

包含 MediaPipe 骨架连接线、关节定义、C3D 标记点映射等常量。
"""
from typing import Dict, Tuple

# ══════════════════════════════════════════════════════════════
#  MediaPipe 骨架连接线定义
# ══════════════════════════════════════════════════════════════
POSE_CONNECTIONS = [
    (11, 13), (13, 15), (15, 17), (15, 19), (17, 19), (12, 14), (14, 16), (16, 18), (16, 20), (18, 20),
    (11, 12), (11, 23), (12, 24), (23, 24), (23, 25), (25, 27), (27, 29), (27, 31), (29, 31),
    (24, 26), (26, 28), (28, 30), (28, 32), (30, 32),
]

# ══════════════════════════════════════════════════════════════
#  MediaPipe 关节定义
# ══════════════════════════════════════════════════════════════
MP_JOINT_DEF: Dict[str, Tuple] = {
    "left_elbow":     (11, 13, 15, "左肘"),   "right_elbow":    (12, 14, 16, "右肘"),
    "left_shoulder":  (13, 11, 23, "左肩"),   "right_shoulder": (14, 12, 24, "右肩"),
    "left_hip":       (11, 23, 25, "左髋"),   "right_hip":      (12, 24, 26, "右髋"),
    "left_knee":      (23, 25, 27, "左膝"),   "right_knee":     (24, 26, 28, "右膝"),
    "left_ankle":     (25, 27, 31, "左踝"),   "right_ankle":    (26, 28, 32, "右踝"),
    "left_wrist":     (13, 15, 17, "左腕"),   "right_wrist":    (14, 16, 18, "右腕"),
}

# ══════════════════════════════════════════════════════════════
#  C3D 默认标记点映射（Vicon PiG 格式）
# ══════════════════════════════════════════════════════════════
DEFAULT_C3D_MAP: Dict[str, Dict] = {
    "left_elbow":     {"markers": ["LSHO", "LELB", "LWRA"], "cn_name": "左肘"},
    "right_elbow":    {"markers": ["RSHO", "RELB", "RWRA"], "cn_name": "右肘"},
    "left_shoulder":  {"markers": ["LELB", "LSHO", "LHIP"], "cn_name": "左肩"},
    "right_shoulder": {"markers": ["RELB", "RSHO", "RHIP"], "cn_name": "右肩"},
    "left_hip":       {"markers": ["LSHO", "LHIP", "LKNE"], "cn_name": "左髋"},
    "right_hip":      {"markers": ["RSHO", "RHIP", "RKNE"], "cn_name": "右髋"},
    "left_knee":      {"markers": ["LHIP", "LKNE", "LANK"], "cn_name": "左膝"},
    "right_knee":     {"markers": ["RHIP", "RKNE", "RANK"], "cn_name": "右膝"},
    "left_ankle":     {"markers": ["LKNE", "LANK", "LTOE"], "cn_name": "左踝"},
    "right_ankle":    {"markers": ["RKNE", "RANK", "RTOE"], "cn_name": "右踝"},
    "left_wrist":     {"markers": ["LELB", "LWRA", "LFIN"], "cn_name": "左腕"},
    "right_wrist":    {"markers": ["RELB", "RWRA", "RFIN"], "cn_name": "右腕"},
}

# ══════════════════════════════════════════════════════════════
#  C3D 预设映射集合
# ══════════════════════════════════════════════════════════════
PRESET_MAPS = {
    "vicon_pig": DEFAULT_C3D_MAP,
    "c3d_generic": {
        "left_elbow":     {"markers": ["L.Shoulder", "L.Elbow", "L.Wrist"], "cn_name": "左肘"},
        "right_elbow":    {"markers": ["R.Shoulder", "R.Elbow", "R.Wrist"], "cn_name": "右肘"},
        "left_shoulder":  {"markers": ["L.Elbow", "L.Shoulder", "L.Hip"], "cn_name": "左肩"},
        "right_shoulder": {"markers": ["R.Elbow", "R.Shoulder", "R.Hip"], "cn_name": "右肩"},
        "left_hip":       {"markers": ["L.Shoulder", "L.Hip", "L.Knee"], "cn_name": "左髋"},
        "right_hip":      {"markers": ["R.Shoulder", "R.Hip", "R.Knee"], "cn_name": "右髋"},
        "left_knee":      {"markers": ["L.Hip", "L.Knee", "L.Ankle"], "cn_name": "左膝"},
        "right_knee":     {"markers": ["R.Hip", "R.Knee", "R.Ankle"], "cn_name": "右膝"},
        "left_ankle":     {"markers": ["L.Knee", "L.Ankle", "L.Toe"], "cn_name": "左踝"},
        "right_ankle":    {"markers": ["R.Knee", "R.Ankle", "R.Toe"], "cn_name": "右踝"},
        "left_wrist":     {"markers": ["L.Elbow", "L.Wrist", "L.Finger"], "cn_name": "左腕"},
        "right_wrist":    {"markers": ["R.Elbow", "R.Wrist", "R.Finger"], "cn_name": "右腕"},
    },
    # ═══════════════════════════════════════════════════════════
    #  适配学校实验室自定义标记点命名
    # ═══════════════════════════════════════════════════════════
    "custom_mocap": {
        # 肘关节：上臂标记 - 肘外侧 - 腕外侧（计算肘屈伸）
        "left_elbow":     {"markers": ["LArm", "LElbowOut", "LWristOut"], "cn_name": "左肘"},
        "right_elbow":    {"markers": ["RArm", "RElbowOut", "RWristOut"], "cn_name": "右肘"},

        # 肩关节：肘外侧 - 肩峰 - 胸骨（计算肩外展/前屈）
        "left_shoulder":  {"markers": ["LElbowOut", "LShoulder", "Chest"], "cn_name": "左肩"},
        "right_shoulder": {"markers": ["RElbowOut", "RShoulder", "Chest"], "cn_name": "右肩"},

        # 髋关节：肩峰 - 髂前上棘(ASIS) - 大腿标记（近似髋部角度）
        "left_hip":       {"markers": ["LShoulder", "LASIS", "LTHI"], "cn_name": "左髋"},
        "right_hip":      {"markers": ["RShoulder", "RASIS", "RTHI"], "cn_name": "右髋"},

        # 膝关节：大腿 - 膝外侧 - 小腿（计算膝屈伸）
        "left_knee":      {"markers": ["LTHI", "LlatKnee", "LShank"], "cn_name": "左膝"},
        "right_knee":     {"markers": ["RTHI", "RlatKnee", "RShank"], "cn_name": "右膝"},

        # 踝关节：小腿 - 踝外侧 - 足趾（计算踝背屈/跖屈）
        "left_ankle":     {"markers": ["LShank", "LAnkleOut", "LToe"], "cn_name": "左踝"},
        "right_ankle":    {"markers": ["RShank", "RAnkleOut", "RToe"], "cn_name": "右踝"},

        # 腕关节（可选）：肘 - 腕外侧 - 手背（近似腕关节角度）
        "left_wrist":     {"markers": ["LElbowOut", "LWristOut", "LHand"], "cn_name": "左腕"},
        "right_wrist":    {"markers": ["RElbowOut", "RWristOut", "RHand"], "cn_name": "右腕"},
    },
}

# ══════════════════════════════════════════════════════════════
#  身体部位分组（用于部位级评分）
# ══════════════════════════════════════════════════════════════
BODY_REGIONS = {
    "upper": ["left_elbow", "right_elbow", "left_shoulder", "right_shoulder", "left_wrist", "right_wrist"],
    "core":  ["left_shoulder", "right_shoulder", "left_hip", "right_hip"],
    "lower": ["left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"]
}

# 部位中文映射（用于前端展示）
REGION_CN = {"upper": "上身", "core": "核心", "lower": "下肢"}
