"""
时序对比模块
包含时序数据对比分析的主函数
"""
from typing import Dict, List
import numpy as np

from config.constants import MP_JOINT_DEF, BODY_REGIONS, REGION_CN
from .preprocessing import fill_nan
from .alignment import best_align_joint, segment_diff


def compare_timeseries(hist_a: list, hist_b: list) -> Dict:
    """
    两阶段时序对比（滑窗起始点 + DTW 分段速度归一）

    每个关节：
      1. best_align_joint()：找起始点 → DTW 路径 → 对齐序列
      2. segment_diff()：分段角度差
      3. 综合评分 = 0.60×r分 + 0.30×DTW分 + 0.10×RMSD分
    """
    MIN_FRAMES = 15
    if len(hist_a) < MIN_FRAMES or len(hist_b) < MIN_FRAMES:
        return {
            "ok": False,
            "reason": f"需要至少{MIN_FRAMES}帧（当前 A:{len(hist_a)} B:{len(hist_b)}）",
            "overall_score": 0.0, "joints": {},
            "n_a": len(hist_a), "n_b": len(hist_b)
        }

    joint_keys = list(MP_JOINT_DEF.keys())
    # 收集各部位的相关系数 r，用于计算部位级评分
    region_rs = {"upper": [], "core": [], "lower": []}

    N_PTS = 200
    joints_out: Dict = {}
    scores: List[float] = []

    for k in joint_keys:
        va = np.array([h["angles"].get(k, np.nan) for h in hist_a], dtype=float)
        vb = np.array([h["angles"].get(k, np.nan) for h in hist_b], dtype=float)
        fa = fill_nan(va)
        fb = fill_nan(vb)
        if fa is None or fb is None:
            continue

        aln = best_align_joint(fa, fb, n_pts=N_PTS)

        r = aln["r"]
        dtw_d = aln["dtw"]
        rmsd = aln["rmsd"]

        # 收集部位相关性数据
        for region, joints in BODY_REGIONS.items():
            if k in joints:
                region_rs[region].append(r)
                break

        # 权重公式：相关性60% | DTW 30% | RMSD 10%
        # 提高形态相似度权重，弱化角度绝对值误差惩罚
        r_score = 50.0 * (r + 1.0)                          # 0-100
        dtw_score = 100.0 * float(np.exp(-dtw_d / 0.8))       # 0-100
        rmsd_score = 100.0 * float(np.exp(-rmsd / 25.0))       # 0-100

        score = round(0.60 * r_score + 0.30 * dtw_score + 0.10 * rmsd_score, 1)

        # 等级判定（保持原有阈值）
        if score >= 85:
            grade = "excellent"
        elif score >= 68:
            grade = "good"
        elif score >= 45:
            grade = "warning"
        else:
            grade = "poor"

        segs = segment_diff(aln["a_aligned"], aln["b_aligned"], n_segs=4)
        diffs = [abs(s["diff"]) for s in segs]
        peak_seg = segs[int(np.argmax(diffs))]

        cn = MP_JOINT_DEF[k][3]
        joints_out[k] = {
            "cn_name": cn,
            "score": score,
            "grade": grade,
            "r": round(r, 3),
            "rmsd": round(rmsd, 1),
            "dtw_score": round(dtw_score, 1),
            "scale": aln["scale"],
            "mean_a": round(float(np.mean(aln["a_aligned"])), 1),
            "mean_b": round(float(np.mean(aln["b_aligned"])), 1),
            "segments": segs,
            "peak_diff": {
                "t_label": f"{round(peak_seg['t_start']*100)}%–{round(peak_seg['t_end']*100)}%",
                "diff": peak_seg["diff"],
                "mean_a": peak_seg["mean_a"],
                "mean_b": peak_seg["mean_b"],
                "direction": peak_seg["direction"],
            },
            "body_region": next((r for r, lst in BODY_REGIONS.items() if k in lst), "other")  # 标记所属部位
        }
        scores.append(score)

    if not scores:
        return {
            "ok": False, "reason": "双侧无共同可用关节",
            "overall_score": 0.0, "joints": {}, "region_scores": {},
            "n_a": len(hist_a), "n_b": len(hist_b)
        }

    # 计算各部位加权相关性评分（新增）
    region_scores = {}
    for region, rs in region_rs.items():
        if rs:
            avg_r = np.mean(rs)
            # 转换为 0-100 分制，并计算参与评估的关节数量
            region_scores[region] = {
                "cn_name": REGION_CN[region],
                "score": round(50.0 * (avg_r + 1.0), 1),  # 部位综合相似度
                "avg_r": round(avg_r, 3),               # 原始相关系数
                "joints_count": len(rs),                # 有效关节数
                "weight": 0.6 if region != "other" else 0  # 在总评分中的理论权重占比提示
            }
        else:
            region_scores[region] = {
                "cn_name": REGION_CN[region],
                "score": 0.0, "avg_r": 0.0, "joints_count": 0, "weight": 0.6
            }

    return {
        "ok": True,
        "overall_score": round(float(np.mean(scores)), 1),
        "joints": joints_out,
        "region_scores": region_scores,  # 新增：上身/核心/下肢三维评分
        "scoring_weights": {             # 新增：权重透明化，便于前端展示
            "correlation": 0.60,
            "dtw": 0.30,
            "rmsd": 0.10
        },
        "n_a": len(hist_a),
        "n_b": len(hist_b),
        "n_pts": N_PTS,
    }
