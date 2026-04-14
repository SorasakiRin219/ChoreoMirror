"""
DTW（动态时间规整）算法模块

包含 DTW 路径计算和最优起始点搜索函数。
"""
from typing import Tuple
import numpy as np


def dtw_path(a: np.ndarray, b: np.ndarray, band_frac: float = 0.3
             ) -> Tuple[float, np.ndarray, np.ndarray]:
    """
    完整 DTW：带回溯，输出规整路径。

    参数
    ----
    a, b       : 两条一维序列（长度可以不同）
    band_frac  : Sakoe-Chiba 带宽，占 max(len_a,len_b) 的比例

    返回
    ----
    dist       : 归一化 DTW 距离
    path_i     : A 的帧索引数组  (沿规整路径等密度采样 N_PATH 点)
    path_j     : B 的帧索引数组  (与 path_i 对应)

    路径意义：path_i[k] 和 path_j[k] 是"同一个动作时刻"的帧。
    """
    na, nb = len(a), len(b)
    band = max(3, int(max(na, nb) * band_frac))
    INF = 1e18

    # ── 前向 DP ─────────────────────────────────────────────────
    D = np.full((na, nb), INF)
    D[0, 0] = (a[0] - b[0]) ** 2
    for j in range(1, min(band + 1, nb)):
        D[0, j] = D[0, j-1] + (a[0] - b[j]) ** 2

    for i in range(1, na):
        lo = max(0, i - band)
        hi = min(nb - 1, i + band)
        for j in range(lo, hi + 1):
            cost = (a[i] - b[j]) ** 2
            D[i, j] = cost + min(
                D[i-1, j],
                D[i, j-1]   if j > lo else INF,
                D[i-1, j-1] if j > lo else INF,
            )

    dist = float(D[na-1, nb-1]) / (na + nb) if D[na-1, nb-1] < INF else INF

    # ── 回溯 → 规整路径 ─────────────────────────────────────────
    path_raw = []
    i, j = na - 1, nb - 1
    while i > 0 or j > 0:
        path_raw.append((i, j))
        if i == 0:
            j -= 1
        elif j == 0:
            i -= 1
        else:
            best = min((D[i-1, j-1], i-1, j-1),
                       (D[i-1, j],   i-1, j),
                       (D[i,   j-1], i,   j-1))
            i, j = best[1], best[2]
    path_raw.append((0, 0))
    path_raw.reverse()

    # 沿路径均匀采样 N_PATH 个点（保证 path_i/path_j 长度固定）
    N_PATH = 200
    path_arr = np.array(path_raw)          # shape (L, 2)
    L = len(path_arr)
    idx_f = np.linspace(0, L - 1, N_PATH)
    path_i = np.round(np.interp(idx_f, np.arange(L), path_arr[:, 0])).astype(int)
    path_j = np.round(np.interp(idx_f, np.arange(L), path_arr[:, 1])).astype(int)
    path_i = np.clip(path_i, 0, na - 1)
    path_j = np.clip(path_j, 0, nb - 1)

    return dist, path_i, path_j


def best_start(comp_a: np.ndarray, comp_b: np.ndarray,
               n_pts: int, n_steps: int = 40) -> Tuple[int, int]:
    """
    阶段一：用合成信号（z-score 均值）的滑动相关找到最优起始帧。

    穷举两侧各自的起始偏移：
      a_off ∈ [0, na//3]  （A 最多跳过前 1/3）
      b_off ∈ [0, nb//3]  （B 最多跳过前 1/3）
    比较长度 = min(na-a_off, nb-b_off)，不再做整体速度缩放。
    速度差异完全交由后续 DTW 路径处理。

    返回 (a_off, b_off)。
    """
    na, nb = len(comp_a), len(comp_b)
    a_steps = max(1, round(na * 0.33) // max(n_steps // 2, 1))
    b_steps = max(1, round(nb * 0.33) // max(n_steps // 2, 1))

    best_r = -np.inf
    best_off = (0, 0)

    for a_off in range(0, round(na * 0.33) + 1, a_steps):
        for b_off in range(0, round(nb * 0.33) + 1, b_steps):
            w = min(na - a_off, nb - b_off)
            if w < max(10, n_pts // 4):
                continue
            av = comp_a[a_off: a_off + w]
            bv = comp_b[b_off: b_off + w]
            sa, sb = av.std(), bv.std()
            if sa < 1e-6 or sb < 1e-6:
                r = 0.0
            else:
                r = float(np.corrcoef(av, bv)[0, 1])
                if np.isnan(r):
                    r = 0.0
            if r > best_r:
                best_r = r
                best_off = (a_off, b_off)

    return best_off
