"""
对称性分析模块，
分析身体左右两侧关节角度的对称性
"""
from typing import Dict


def analyze_symmetry(angles: Dict) -> Dict:
    """
    分析身体左右两侧关节的对称性

    Args:
        angles: 关节角度字典，来自extract_mp_angles

    Returns:
        包含各关节对对称性分析的字典：
        {
            "关节名称": {
                "left": float,
                "right": float,
                "diff": float,
                "symmetric": bool
            },
            ...
        }
    """
    # 定义左右对应的关节对
    pairs = [
        ("left_elbow", "right_elbow", "肘关节"),
        ("left_shoulder", "right_shoulder", "肩关节"),
        ("left_hip", "right_hip", "髋关节"),
        ("left_knee", "right_knee", "膝关节"),
        ("left_ankle", "right_ankle", "踝关节")
    ]

    result = {}
    for left_key, right_key, joint_name in pairs:
        if left_key in angles and right_key in angles:
            left_angle = angles[left_key]["angle"]
            right_angle = angles[right_key]["angle"]
            diff = abs(left_angle - right_angle)

            result[joint_name] = {
                "left": left_angle,
                "right": right_angle,
                "diff": round(diff, 1),
                "symmetric": diff < 15  # 差异小于15度视为对称
            }

    return result
