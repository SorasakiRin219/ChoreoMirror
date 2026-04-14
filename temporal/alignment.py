"""
对齐算法模块

包含单关节对齐、全局对齐和分段差异计算函数。
"""
from typing import List
import numpy as np

from config.constants import MP_JOINT_DEF, BODY_REGIONS, REGION_CN
from .preprocessing import fill_nan, resample
from .dtw import dtw_path, best_start


def _znorm(x: np.ndarray) -> np.ndarray:
    """Z-score 标准化"""
    s = x.std()
    return (x - x.mean()) / s if s > 0.5 else x - x.mean()


def best_align_joint(a_raw: np.ndarray, b_raw: np.ndarray,
                     n_pts: int = 200) -> dict:
    """
    单关节两阶段对齐：
      阶段一：滑动窗口找最优起始偏移 (a_off, b_off)
      阶段二：DTW 规整路径沿路径采样，得到真正分段速度归一的对齐序列

    a_aligned / b_aligned 是沿 DTW 路径采样的角度序列：
    a_aligned[k] 和 b_aligned[k] 对应动作的"同一时刻"。
    """
    na, nb = len(a_raw), len(b_raw)

    a_z = _znorm(a_raw)
    b_z = _znorm(b_raw)

    # 阶段一：滑窗找起始点
    a_off, b_off = best_start(a_z, b_z, n_pts=n_pts, n_steps=40)

    seg_az = a_z[a_off:]
    seg_bz = b_z[b_off:]

    # 阶段二：DTW 规整路径
    dtw_d, path_i, path_j = dtw_path(seg_az, seg_bz, band_frac=0.35)

    # 沿路径采样原始角度序列 → 这就是分段速度归一后的对齐结果
    a_aln = a_raw[a_off:][np.clip(path_i, 0, len(seg_az) - 1)]
    b_aln = b_raw[b_off:][np.clip(path_j, 0, len(seg_bz) - 1)]

    rmsd = float(np.sqrt(np.mean((a_aln - b_aln) ** 2)))

    # Pearson r 在 z-score 对齐序列上计算
    az_samp = _znorm(a_aln)
    bz_samp = _znorm(b_aln)
    sa, sb = az_samp.std(), bz_samp.std()
    if sa < 1e-6 or sb < 1e-6:
        r = 0.0
    else:
        r = float(np.corrcoef(az_samp, bz_samp)[0, 1])
        if np.isnan(r):
            r = 0.0

    return {
        "a_off": a_off,
        "b_off": b_off,
        "scale": round(nb / max(na, 1), 3),
        "r": round(r, 3),
        "dtw": round(dtw_d, 4),
        "rmsd": round(rmsd, 1),
        "a_aligned": a_aln,
        "b_aligned": b_aln,
    }


def composite_global_align(hist_a: list, hist_b: list,
                          n_pts: int = 200) -> dict:
    """
    全局两阶段对齐（作用于骨架帧映射）：
      阶段一：滑动窗口找最优 (a_off, b_off) 起始帧
      阶段二：DTW 规整路径给出分段速度归一的 (path_i, path_j)

    path_i[k] 是 A 在对齐段内的帧偏移，path_j[k] 对应 B 的帧偏移。
    骨架映射：
      original_A_frame[k] = a_off + path_i[k]  (映射回 hist_a 索引)
      original_B_frame[k] = b_off + path_j[k]  (映射回 hist_b 索引)
    """
    JOINT_KEYS = list(MP_JOINT_DEF.keys())
    n_a = len(hist_a)
    n_b = len(hist_b)

    def build_composite(hist, nk):
        mats = []
        for k in JOINT_KEYS:
            arr = np.array([h["angles"].get(k, np.nan) for h in hist], dtype=float)
            arr = fill_nan(arr)
            if arr is None:
                continue
            arr = resample(arr, nk)
            s = arr.std()
            if s < 1.0:
                continue
            mats.append((arr - arr.mean()) / s)
        return np.mean(mats, axis=0) if mats else np.zeros(nk)

    comp_a = build_composite(hist_a, n_a)   # 原始帧数，不重采样
    comp_b = build_composite(hist_b, n_b)

    # 阶段一：找最优起始帧（以原始帧数索引）
    a_off, b_off = best_start(comp_a, comp_b, n_pts=n_pts, n_steps=40)

    # 提取对齐段
    seg_a = comp_a[a_off:]
    seg_b = comp_b[b_off:]

    # 阶段二：DTW 规整路径
    _, path_i, path_j = dtw_path(seg_a, seg_b, band_frac=0.35)

    # path_i / path_j 是段内偏移，转为 hist 原始索引
    frame_a = np.clip(a_off + path_i, 0, n_a - 1).tolist()
    frame_b = np.clip(b_off + path_j, 0, n_b - 1).tolist()

    return {
        "a_off": a_off,
        "b_off": b_off,
        "frame_a": frame_a,   # 长度 N_PATH=200，每个是 hist_a 的帧索引
        "frame_b": frame_b,   # 同上，对应 hist_b
        "n_pts": 200,
    }


def segment_diff(a_aligned: np.ndarray, b_aligned: np.ndarray,
                n_segs: int = 4) -> List[dict]:
    """
    将对齐后的序列等分为 n_segs 个时间窗口，
    每段返回 {t_start, t_end, mean_a, mean_b, diff, direction}
    """
    n = len(a_aligned)
    segs = []
    for i in range(n_segs):
        s = i * n // n_segs
        e = (i + 1) * n // n_segs
        ma = float(np.mean(a_aligned[s:e]))
        mb = float(np.mean(b_aligned[s:e]))
        segs.append({
            "t_start": round(i / n_segs, 2),
            "t_end": round((i + 1) / n_segs, 2),
            "mean_a": round(ma, 1),
            "mean_b": round(mb, 1),
            "diff": round(ma - mb, 1),
            "direction": "偏大" if ma > mb else "偏小",
        })
    return segs
